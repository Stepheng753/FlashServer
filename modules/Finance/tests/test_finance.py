import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.Finance import db as finance_db
from modules.Finance.routes import finance_bp
from modules.Finance.simplefin_client import (
    decode_claim_token,
    normalize_institution_name,
    extract_masks_and_digits,
    infer_account_type,
    match_existing_account,
    claim_access_url,
)


def make_account(acc_id, account_type, balance, **extra):
    acc = {
        "id": acc_id,
        "institution": extra.pop("institution", "Test Bank"),
        "name": extra.pop("name", acc_id),
        "account_type": account_type,
        "balance": balance,
        "is_asset": 0 if account_type in ("credit", "mortgage", "loan") else 1,
    }
    acc.update(extra)
    return acc


class FinanceDbTestCase(unittest.TestCase):
    """Runs every test against a throwaway SQLite file instead of data/finance.db."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(finance_db, "DB_PATH", os.path.join(self.tmp.name, "finance_test.db"))
        self.db_patch.start()
        finance_db.init_db()

    def tearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()


class TestFinanceDb(FinanceDbTestCase):

    def test_init_db_creates_tables_and_is_idempotent(self):
        finance_db.init_db()
        with finance_db.get_connection() as conn:
            names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ("accounts", "snapshots", "account_snapshots", "settings", "budget_items"):
            self.assertIn(table, names)

    def test_upsert_and_get_account(self):
        finance_db.upsert_account(make_account("a1", "checking", 1500.0))
        acc = finance_db.get_account_by_id("a1")
        self.assertEqual(acc["balance"], 1500.0)
        finance_db.upsert_account(make_account("a1", "checking", 2000.0))
        self.assertEqual(finance_db.get_account_by_id("a1")["balance"], 2000.0)
        self.assertEqual(len(finance_db.get_accounts()), 1)
        self.assertIsNone(finance_db.get_account_by_id("missing"))

    def test_accounts_sorted_by_category_then_balance(self):
        finance_db.upsert_account(make_account("inv", "investment", 100.0))
        finance_db.upsert_account(make_account("chk_small", "checking", 10.0))
        finance_db.upsert_account(make_account("chk_big", "checking", 500.0))
        finance_db.upsert_account(make_account("cc", "credit", -50.0))
        ids = [a["id"] for a in finance_db.get_accounts()]
        self.assertEqual(ids, ["chk_big", "chk_small", "cc", "inv"])

    def test_update_account_metadata(self):
        finance_db.upsert_account(make_account("a1", "checking", 100.0))
        self.assertTrue(finance_db.update_account_metadata("a1", name="  Renamed ", account_type="SAVINGS", balance="250.5"))
        acc = finance_db.get_account_by_id("a1")
        self.assertEqual(acc["name"], "Renamed")
        self.assertEqual(acc["account_type"], "savings")
        self.assertEqual(acc["balance"], 250.5)
        self.assertFalse(finance_db.update_account_metadata("a1"))
        self.assertFalse(finance_db.update_account_metadata("missing", name="x"))

    def test_delete_account_removes_snapshots_and_order_entries(self):
        finance_db.upsert_account(make_account("a1", "checking", 100.0))
        finance_db.upsert_account(make_account("a2", "checking", 200.0))
        finance_db.record_snapshot()
        finance_db.set_setting("account_order_cash", json.dumps(["a1", "a2"]))
        finance_db.delete_account("a1")
        self.assertIsNone(finance_db.get_account_by_id("a1"))
        self.assertEqual(json.loads(finance_db.get_setting("account_order_cash")), ["a2"])
        with finance_db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM account_snapshots WHERE account_id = 'a1'").fetchall()
        self.assertEqual(rows, [])

    def test_settings_roundtrip(self):
        self.assertEqual(finance_db.get_setting("nope", "fallback"), "fallback")
        finance_db.set_setting("k", 5)
        self.assertEqual(finance_db.get_setting("k"), "5")
        finance_db.set_setting("k", "six")
        self.assertEqual(finance_db.get_setting("k"), "six")

    def test_record_snapshot_without_accounts_returns_none(self):
        self.assertIsNone(finance_db.record_snapshot())


class TestFinanceSummaryAndHistory(FinanceDbTestCase):

    def setUp(self):
        super().setUp()
        finance_db.upsert_account(make_account("chk", "checking", 1000.0))
        finance_db.upsert_account(make_account("sav", "savings", 4000.0))
        finance_db.upsert_account(make_account("brk", "investment", 10000.0, vested_balance=8000.0))
        finance_db.upsert_account(make_account("home", "property", 500000.0))
        finance_db.upsert_account(make_account("mort", "mortgage", -300000.0))
        finance_db.upsert_account(make_account("cc", "credit", -500.0, credit_limit=5000.0))

    def test_summary_metrics(self):
        s = finance_db.get_summary()
        self.assertEqual(s["liquid_cash"], 5000.0)
        self.assertEqual(s["investments"], 10000.0)
        self.assertEqual(s["vested_investments"], 8000.0)
        self.assertEqual(s["property_value"], 500000.0)
        self.assertEqual(s["mortgage_debt"], 300000.0)
        self.assertEqual(s["credit_debt"], -500.0)
        self.assertEqual(s["total_assets"], 515000.0)
        self.assertEqual(s["total_liabilities"], 300500.0)
        self.assertEqual(s["net_worth"], 214500.0)
        self.assertEqual(s["home_equity"], 200000.0)
        self.assertEqual(s["credit_utilization"], 10.0)
        self.assertEqual(s["accounts_count"], 6)
        self.assertEqual(len(s["categories"]["cash"]), 2)
        self.assertEqual(len(s["categories"]["mortgage"]), 1)

    def test_snapshot_matches_summary_and_feeds_history(self):
        snap_id = finance_db.record_snapshot(note="unit test", net_worth_change=12.345)
        self.assertIsNotNone(snap_id)
        hist = finance_db.get_historical_snapshots("all")
        self.assertEqual(hist["count"], 1)
        self.assertEqual(hist["net_worth"], [214500.0])
        self.assertEqual(hist["assets"], [515000.0])
        self.assertEqual(hist["liabilities"], [300500.0])
        self.assertEqual(finance_db.get_summary()["net_worth_change"], 12.35)

    def test_net_worth_change_carries_forward(self):
        finance_db.record_snapshot(net_worth_change=50.0)
        finance_db.record_snapshot()
        self.assertEqual(finance_db.get_summary()["net_worth_change"], 50.0)

    def test_history_timeframes_filter_old_rows(self):
        finance_db.record_snapshot()
        with finance_db.get_connection() as conn:
            conn.execute("""
                INSERT INTO snapshots (timestamp, net_worth, total_assets, total_liabilities,
                    liquid_cash, investments, mortgage_debt, credit_debt, note)
                VALUES ('2020-01-15T12:00:00-08:00', 1, 1, 0, 1, 0, 0, 0, 'old')
            """)
            conn.commit()
        self.assertEqual(finance_db.get_historical_snapshots("all")["count"], 2)
        for tf in ("1m", "3m", "6m", "1y"):
            self.assertEqual(finance_db.get_historical_snapshots(tf)["count"], 1, tf)
        self.assertEqual(finance_db.get_historical_snapshots(None)["timeframe"], "all")


class TestBudget(FinanceDbTestCase):

    def test_upsert_get_toggle_delete(self):
        rent = finance_db.upsert_budget_item({"category": "expense", "name": "Rent", "amount": 2000})
        pay = finance_db.upsert_budget_item({
            "category": "income", "name": "Salary", "amount": 6000, "tax_status": "post-tax",
            "details_json": {"gross": 9000},
        })
        self.assertEqual(finance_db.get_budget_item_by_id(pay)["details"], {"gross": 9000})
        self.assertEqual(len(finance_db.get_budget_items()), 2)
        self.assertEqual([i["name"] for i in finance_db.get_budget_items("expense")], ["Rent"])

        finance_db.upsert_budget_item({"id": rent, "category": "expense", "name": "Rent", "amount": 2100})
        self.assertEqual(finance_db.get_budget_item_by_id(rent)["amount"], 2100.0)

        self.assertTrue(finance_db.toggle_budget_item_active(rent))
        self.assertEqual(finance_db.get_budget_item_by_id(rent)["is_active"], 0)
        self.assertTrue(finance_db.toggle_budget_item_active(rent))
        self.assertEqual(finance_db.get_budget_item_by_id(rent)["is_active"], 1)

        self.assertTrue(finance_db.delete_budget_item(rent))
        self.assertFalse(finance_db.delete_budget_item(rent))
        self.assertIsNone(finance_db.get_budget_item_by_id(rent))
        self.assertFalse(finance_db.toggle_budget_item_active(9999))

    def test_budget_summary_ignores_inactive_and_splits_pretax(self):
        finance_db.upsert_budget_item({"category": "income", "name": "Salary", "amount": 5000, "tax_status": "post-tax"})
        finance_db.upsert_budget_item({"category": "income", "name": "Gross 401k", "amount": 1000, "tax_status": "pre-tax"})
        finance_db.upsert_budget_item({"category": "expense", "name": "Rent", "amount": 2000})
        off = finance_db.upsert_budget_item({"category": "expense", "name": "Gym", "amount": 50})
        finance_db.toggle_budget_item_active(off)
        s = finance_db.get_budget_summary()
        self.assertEqual(s["total_monthly_income_posttax"], 5000.0)
        self.assertEqual(s["total_monthly_income_pretax"], 1000.0)
        self.assertEqual(s["total_income_combined"], 6000.0)
        self.assertEqual(s["total_monthly_expenses"], 2000.0)
        self.assertEqual(s["net_monthly_cash_flow"], 3000.0)
        self.assertEqual(len(s["incomes"]), 2)
        self.assertEqual(len(s["expenses"]), 2)


class TestSimpleFinHelpers(unittest.TestCase):

    def test_decode_claim_token(self):
        import base64
        url = "https://bridge.example.org/simplefin/claim/abc123"
        self.assertEqual(decode_claim_token(url), url)
        self.assertEqual(decode_claim_token(base64.b64encode(url.encode()).decode()), url)
        self.assertEqual(
            decode_claim_token("  plain-token "),
            "https://beta-bridge.simplefin.org/simplefin/claim/plain-token",
        )

    def test_normalize_institution_name(self):
        self.assertEqual(normalize_institution_name(""), "")
        self.assertEqual(normalize_institution_name("Chase Bank"), normalize_institution_name("chase"))
        self.assertEqual(normalize_institution_name("Charles Schwab Corporation"), "charlesschwab")

    def test_extract_masks_and_digits(self):
        self.assertEqual(extract_masks_and_digits(""), [])
        self.assertIn("1234", extract_masks_and_digits("Checking ...1234"))
        self.assertIn("5678", extract_masks_and_digits("Visa ending in 5678"))

    def test_infer_account_type(self):
        cases = [
            ("Home Mortgage", "Lender", -200000, "mortgage"),
            ("Roth IRA", "Fidelity", 100, "retirement"),
            ("Brokerage", "Schwab", 100, "investment"),
            ("Freedom Visa", "Chase", -50, "credit"),
            ("High Yield Savings", "Ally", 100, "savings"),
            ("Everyday Checking", "Bank", 100, "checking"),
            ("Mystery", "Org", -5000, "loan"),
            ("Mystery", "Org", 5, "checking"),
        ]
        for name, org, bal, expected in cases:
            self.assertEqual(infer_account_type(name, org, bal), expected, name)

    def test_match_existing_account_by_simplefin_id(self):
        existing = [
            {"id": "a1", "simplefin_id": "ACT-1"},
            {"id": "sf_ACT-2", "simplefin_id": None},
            {"id": "a3", "simplefin_id": None},
        ]
        self.assertEqual(match_existing_account(existing, {"id": "ACT-1"})["id"], "a1")
        self.assertEqual(match_existing_account(existing, {"id": "ACT-2"})["id"], "sf_ACT-2")
        self.assertIsNone(match_existing_account(existing, {"id": ""}))
        self.assertIsNone(match_existing_account(existing, {"id": "UNKNOWN", "name": "zzz", "balance": 1}))

    def test_match_existing_account_respects_used_ids(self):
        existing = [{"id": "a1", "simplefin_id": "ACT-1"}]
        self.assertIsNone(match_existing_account(existing, {"id": "ACT-1"}, used_ids={"a1"}))


class TestClaimAccessUrl(FinanceDbTestCase):

    class FakeResponse:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

    def test_claim_success_stores_url(self):
        resp = self.FakeResponse(200, "https://user:pw@bridge.example.org/simplefin\n")
        with patch("modules.Finance.simplefin_client.requests.post", return_value=resp), \
             patch("modules.Finance.simplefin_client.save_secret") as save:
            result = claim_access_url("https://bridge.example.org/claim/xyz")
        self.assertTrue(result["success"])
        save.assert_called_once_with("SIMPLEFIN_ACCESS_URL", "https://user:pw@bridge.example.org/simplefin")

    def test_claim_failure_modes(self):
        with patch("modules.Finance.simplefin_client.requests.post", return_value=self.FakeResponse(403, "nope")):
            self.assertFalse(claim_access_url("https://bridge.example.org/claim/xyz")["success"])
        with patch("modules.Finance.simplefin_client.requests.post", return_value=self.FakeResponse(200, "garbage")):
            self.assertFalse(claim_access_url("https://bridge.example.org/claim/xyz")["success"])
        import requests
        with patch("modules.Finance.simplefin_client.requests.post", side_effect=requests.exceptions.ConnectionError("down")):
            result = claim_access_url("https://bridge.example.org/claim/xyz")
        self.assertFalse(result["success"])
        self.assertIn("Failed to reach", result["error"])


class TestFinanceRoutes(FinanceDbTestCase):

    def setUp(self):
        super().setUp()
        app = Flask(__name__)
        app.register_blueprint(finance_bp)
        self.client = app.test_client()
        # Never touch the real config/secrets.json
        self.secret_patch = patch("modules.Finance.routes.save_secret")
        self.save_secret = self.secret_patch.start()

    def tearDown(self):
        self.secret_patch.stop()
        super().tearDown()

    def test_dashboard_page_renders(self):
        resp = self.client.get("/finance")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"<html", resp.data.lower())

    def test_empty_summary_accounts_history(self):
        self.assertEqual(self.client.get("/api/finance/summary").get_json()["data"]["net_worth"], 0)
        self.assertEqual(self.client.get("/api/finance/accounts").get_json()["accounts"], [])
        hist = self.client.get("/api/finance/history?timeframe=1y").get_json()
        self.assertEqual(hist["data"]["count"], 0)

    def test_add_update_delete_manual_account(self):
        self.assertEqual(self.client.post("/api/finance/account/add", json={"name": " "}).status_code, 400)

        resp = self.client.post("/api/finance/account/add", json={
            "name": "Rental House", "account_type": "property_mortgage", "balance": 250000,
        })
        self.assertEqual(resp.status_code, 200)
        acc = resp.get_json()["account"]
        self.assertEqual(acc["account_type"], "property")
        self.assertEqual(acc["is_asset"], 1)
        self.assertEqual(acc["is_manual"], 1)
        acc_id = acc["id"]

        loan = self.client.post("/api/finance/accounts/add", json={
            "name": "Rental Loan", "account_type": "mortgage", "balance": -100000,
        }).get_json()["account"]
        self.assertEqual(loan["account_type"], "mortgage")
        self.assertEqual(loan["is_asset"], 0)

        card = self.client.post("/api/finance/account/add", json={
            "name": "Card", "account_type": "credit_card", "balance": -20, "credit_limit": 1000,
        }).get_json()["account"]
        self.assertEqual(card["account_type"], "credit")

        summary = self.client.get("/api/finance/summary").get_json()["data"]
        self.assertEqual(summary["property_value"], 250000.0)
        self.assertEqual(summary["mortgage_debt"], 100000.0)
        self.assertEqual(summary["credit_utilization"], 2.0)

        # Update: balance flips negative -> reclassified as mortgage
        resp = self.client.post(f"/api/finance/account/{acc_id}", json={
            "account_type": "property_mortgage", "balance": -5, "name": "Renamed House",
        })
        self.assertEqual(resp.status_code, 200)
        updated = finance_db.get_account_by_id(acc_id)
        self.assertEqual(updated["account_type"], "mortgage")
        self.assertEqual(updated["name"], "Renamed House")

        self.assertEqual(self.client.post("/api/finance/account/nope", json={"name": "x"}).status_code, 404)

        self.assertEqual(self.client.delete(f"/api/finance/account/{acc_id}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/finance/account/{acc_id}").status_code, 404)
        self.assertEqual(self.client.post(f"/api/finance/account/{acc_id}/delete").status_code, 404)

    def test_account_order_settings(self):
        self.assertEqual(self.client.post("/api/finance/settings/order", json={"category": "cash"}).status_code, 200)
        resp = self.client.post("/api/finance/settings/order", json={"category": "cash", "order": ["b", "a"]})
        self.assertTrue(resp.get_json()["success"])
        self.assertEqual(self.client.post("/api/finance/settings/order", json={"order": ["a"]}).status_code, 400)
        orders = self.client.get("/api/finance/settings/order").get_json()["orders"]
        self.assertEqual(orders["cash"], ["b", "a"])
        self.assertEqual(orders["credit"], [])

    def test_budget_endpoints(self):
        self.assertEqual(self.client.post("/api/finance/budget/item", json={"name": ""}).status_code, 400)
        resp = self.client.post("/api/finance/budget/item", json={"category": "expense", "name": "Rent", "amount": 1500})
        item_id = resp.get_json()["item_id"]

        self.assertEqual(self.client.get(f"/api/finance/budget/item/{item_id}").get_json()["item"]["name"], "Rent")
        self.assertEqual(self.client.get("/api/finance/budget/item/9999").status_code, 404)

        budget = self.client.get("/api/finance/budget").get_json()["data"]
        self.assertEqual(budget["total_monthly_expenses"], 1500.0)

        self.assertEqual(self.client.post(f"/api/finance/budget/toggle/{item_id}").status_code, 200)
        self.assertEqual(self.client.get("/api/finance/budget").get_json()["data"]["total_monthly_expenses"], 0.0)
        self.assertEqual(self.client.post("/api/finance/budget/toggle/9999").status_code, 404)

        self.assertEqual(self.client.delete(f"/api/finance/budget/item/{item_id}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/finance/budget/item/{item_id}").status_code, 404)

    def test_claim_validation_and_direct_access_url(self):
        self.assertEqual(self.client.post("/api/finance/claim", json={}).status_code, 400)
        resp = self.client.post("/api/finance/claim", json={"access_url": "https://u:p@bridge.example.org/sf"})
        self.assertTrue(resp.get_json()["success"])
        self.save_secret.assert_called_with("SIMPLEFIN_ACCESS_URL", "https://u:p@bridge.example.org/sf")
        self.assertEqual(finance_db.get_setting("simplefin_access_url"), "https://u:p@bridge.example.org/sf")

    def test_settings_masks_access_url_and_disconnect_clears(self):
        finance_db.set_setting("simplefin_access_url", "https://secret:pw@bridge.example.org/sf")
        with patch("modules.Finance.simplefin_client.get_secret", return_value=None):
            data = self.client.get("/api/finance/settings").get_json()
        self.assertTrue(data["connected"])
        self.assertEqual(data["masked_url"], "https://***:***@bridge.example.org/sf")
        self.assertNotIn("secret", json.dumps(data))

        self.assertTrue(self.client.post("/api/finance/disconnect").get_json()["success"])
        self.assertEqual(finance_db.get_setting("simplefin_access_url"), "")

    def test_sync_without_connection_records_baseline_snapshot(self):
        finance_db.upsert_account(make_account("a1", "checking", 100.0))
        with patch("modules.Finance.simplefin_client.get_secret", return_value=None):
            resp = self.client.post("/api/finance/sync")
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(data["is_simulated"])
        self.assertEqual(finance_db.get_historical_snapshots("all")["count"], 1)
        self.assertTrue(finance_db.get_setting("simplefin_last_sync"))


class FakeBridgeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class TestSimpleFinSync(FinanceDbTestCase):

    ACCESS_URL = "https://user:pw@bridge.example.org/simplefin"

    def sync(self, response=None, error=None):
        from modules.Finance.simplefin_client import sync_simplefin_accounts
        kwargs = {"side_effect": error} if error else {"return_value": response}
        with patch("modules.Finance.simplefin_client.get_secret", return_value=self.ACCESS_URL), \
             patch("modules.Finance.simplefin_client.requests.get", **kwargs) as get:
            result = sync_simplefin_accounts()
        return result, get

    def test_sync_creates_new_accounts_and_authenticates(self):
        payload = {"accounts": [
            {"id": "ACT-1", "name": "Everyday Checking", "balance": "1200.50", "org": {"name": "Test Bank"}},
            {"id": "ACT-2", "name": "Freedom Visa", "balance": "-300", "org": {"name": "Chase"}},
        ]}
        result, get = self.sync(FakeBridgeResponse(200, payload))
        self.assertTrue(result["success"])
        self.assertFalse(result["is_simulated"])
        self.assertEqual(result["total_checked"], 2)

        args, kwargs = get.call_args
        self.assertEqual(args[0], "https://bridge.example.org/simplefin/accounts")
        self.assertEqual(kwargs["auth"], ("user", "pw"))

        chk = finance_db.get_account_by_id("sf_ACT-1")
        self.assertEqual(chk["account_type"], "checking")
        self.assertEqual(chk["balance"], 1200.5)
        card = finance_db.get_account_by_id("sf_ACT-2")
        self.assertEqual(card["account_type"], "credit")
        self.assertEqual(card["is_asset"], 0)
        self.assertEqual(finance_db.get_historical_snapshots("all")["count"], 1)

    def test_sync_updates_existing_account_and_tracks_balance_change(self):
        finance_db.upsert_account(make_account("mine", "checking", 100.0, simplefin_id="ACT-1", name="My Checking"))
        payload = {"accounts": [{"id": "ACT-1", "name": "Checking", "balance": 175.25, "org": {"name": "Test Bank"}}]}
        result, _ = self.sync(FakeBridgeResponse(200, payload))
        self.assertTrue(result["success"])
        acc = finance_db.get_account_by_id("mine")
        self.assertEqual(acc["balance"], 175.25)
        self.assertEqual(acc["name"], "My Checking")  # user-edited name preserved
        self.assertEqual(acc["balance_change"], 75.25)
        self.assertEqual(len(finance_db.get_accounts()), 1)

    def test_net_worth_change_is_the_difference_between_the_last_two_syncs(self):
        def payload(balance):
            return FakeBridgeResponse(200, {"accounts": [
                {"id": "ACT-1", "name": "Everyday Checking", "balance": balance, "org": {"name": "Test Bank"}}]})

        self.sync(payload(1000))                                    # first sync: account is new
        self.assertEqual(finance_db.get_summary()["net_worth_change"], 0.0)
        self.sync(payload(1250.50))                                 # second sync: balance moved
        self.assertEqual(finance_db.get_summary()["net_worth"], 1250.5)
        self.assertEqual(finance_db.get_summary()["net_worth_change"], 250.5)
        self.sync(payload(1250.50))                                 # nothing changed upstream
        self.assertEqual(finance_db.get_summary()["net_worth_change"], 250.5)
        self.sync(payload(1000))                                    # drops back
        self.assertEqual(finance_db.get_summary()["net_worth_change"], -250.5)

    def test_net_worth_change_sums_every_account_that_moved(self):
        def payload(a, b):
            return FakeBridgeResponse(200, {"accounts": [
                {"id": "A", "name": "Everyday Checking", "balance": a, "org": {"name": "Bank"}},
                {"id": "B", "name": "Freedom Visa", "balance": b, "org": {"name": "Chase"}}]})
        self.sync(payload(1000, -100))
        self.sync(payload(1100, -400))       # +100 cash, -300 more card debt
        self.assertEqual(finance_db.get_summary()["net_worth_change"], -200.0)

    def test_sync_positive_mortgage_is_stored_as_liability(self):
        payload = {"accounts": [{"id": "M1", "name": "Home Mortgage", "balance": 250000, "org": {"name": "Lender"}}]}
        self.sync(FakeBridgeResponse(200, payload))
        acc = finance_db.get_account_by_id("sf_M1")
        self.assertEqual(acc["account_type"], "mortgage")
        self.assertEqual(acc["balance"], -250000.0)

    def test_sync_bridge_errors(self):
        result, _ = self.sync(FakeBridgeResponse(403, text="forbidden"))
        self.assertFalse(result["success"])
        self.assertIn("403", result["error"])

        import requests
        result, _ = self.sync(error=requests.exceptions.Timeout("slow"))
        self.assertFalse(result["success"])
        self.assertIn("Connection error", result["error"])


if __name__ == "__main__":
    unittest.main()
