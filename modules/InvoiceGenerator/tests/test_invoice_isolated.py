"""InvoiceGenerator tests that run against a throwaway SQLite file, never data/invoices.db."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from flask import Flask

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.InvoiceGenerator import db as inv_db
from modules.InvoiceGenerator.config import APP_TIMEZONE
from modules.InvoiceGenerator.pdf import format_currency, format_phone as pdf_format_phone
from modules.InvoiceGenerator.routes import invoice_bp

TEMPLATE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def future(days):
    return (datetime.now(APP_TIMEZONE) + timedelta(days=days)).strftime("%Y-%m-%d")


class InvoiceDbTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(inv_db, "DB_PATH", os.path.join(self.tmp.name, "invoices_test.db"))
        self.patch.start()
        inv_db.init_db()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def make_client(self, name="Acme Corp", **kw):
        return inv_db.add_client(name, **kw)

    def make_invoice(self, client_id=None, **extra):
        data = {
            "client_id": client_id, "client_name": "Acme Corp", "issue_date": "2030-01-10", "due_date": "2030-02-10",
            "items": [{"description": "Tutoring", "quantity": 2, "unit_price": 50}],
        }
        data.update(extra)
        return inv_db.create_invoice(data)


class TestFormatting(unittest.TestCase):

    def test_phone_formats(self):
        for fn in (inv_db.format_phone, pdf_format_phone):
            self.assertEqual(fn("(619) 555-1234"), "+1 (619) 555-1234")
            self.assertEqual(fn("1-619-555-1234"), "+1 (619) 555-1234")
            self.assertEqual(fn(""), "")
            self.assertEqual(fn("12345"), "12345")

    def test_currency(self):
        self.assertEqual(format_currency(1234.5), "$1,234.50")
        self.assertEqual(format_currency("oops"), "$0.00")
        self.assertEqual(format_currency(None), "$0.00")


class TestSenders(InvoiceDbTestCase):

    def test_default_sender_is_seeded_and_listed_first(self):
        senders = inv_db.get_senders()
        self.assertEqual(len(senders), 1)
        self.assertEqual(senders[0]["is_default"], 1)
        other = inv_db.add_sender("Side Biz")
        self.assertEqual(inv_db.get_senders()[0]["id"], senders[0]["id"])
        self.assertEqual(inv_db.get_sender_by_id(other)["name"], "Side Biz")

    def test_only_one_default_at_a_time(self):
        first = inv_db.get_senders()[0]["id"]
        second = inv_db.add_sender("New Default", is_default=1)
        self.assertEqual([s["id"] for s in inv_db.get_senders() if s["is_default"]], [second])
        self.assertTrue(inv_db.set_default_sender(first))
        self.assertEqual([s["id"] for s in inv_db.get_senders() if s["is_default"]], [first])
        self.assertTrue(inv_db.update_sender(second, "New Default", is_default=1))
        self.assertEqual([s["id"] for s in inv_db.get_senders() if s["is_default"]], [second])

    def test_setting_default_on_missing_sender_keeps_current_default(self):
        current = inv_db.get_senders()[0]["id"]
        self.assertFalse(inv_db.set_default_sender(999))
        self.assertEqual([s["id"] for s in inv_db.get_senders() if s["is_default"]], [current])

    def test_missing_sender_operations(self):
        self.assertIsNone(inv_db.get_sender_by_id(999))
        self.assertFalse(inv_db.update_sender(999, "x"))
        self.assertFalse(inv_db.delete_sender(999))

    def test_phone_is_normalized_on_save(self):
        sid = inv_db.add_sender("Phoney", phone="6195551234")
        self.assertEqual(inv_db.get_sender_by_id(sid)["phone"], "+1 (619) 555-1234")


class TestInvoiceCalculations(InvoiceDbTestCase):

    def test_totals_with_discount_and_tax(self):
        inv_id = self.make_invoice(discount_amount=20, tax_rate=10)
        inv = inv_db.get_invoice_by_id(inv_id)
        self.assertEqual(inv["subtotal"], 100.0)
        self.assertEqual(inv["total_amount"], 88.0)
        self.assertEqual(inv["items"][0]["amount"], 100.0)

    def test_discount_cannot_push_total_negative_and_negatives_are_floored(self):
        inv = inv_db.get_invoice_by_id(self.make_invoice(discount_amount=500, tax_rate=-5))
        self.assertEqual(inv["total_amount"], 0.0)
        self.assertEqual(inv["tax_rate"], 0.0)

    def test_blank_items_skipped_and_bad_numbers_default(self):
        inv_id = inv_db.create_invoice({
            "client_name": "X",
            "items": [{"description": "  "}, {"description": "Good", "quantity": "abc", "unit_price": "10"},
                      {"description": "Free", "unit_price": "oops"}],
        })
        items = inv_db.get_invoice_by_id(inv_id)["items"]
        self.assertEqual([(i["description"], i["quantity"], i["amount"]) for i in items], [("Good", 1.0, 10.0), ("Free", 1.0, 0.0)])

    def test_number_generation_and_explicit_number(self):
        year = datetime.now(APP_TIMEZONE).year
        self.assertEqual(inv_db.generate_next_invoice_number(), f"INV-{year}-001")
        first = inv_db.get_invoice_by_id(self.make_invoice())["invoice_number"]
        second = inv_db.get_invoice_by_id(self.make_invoice())["invoice_number"]
        self.assertEqual((first, second), (f"INV-{year}-001", f"INV-{year}-002"))
        custom = inv_db.get_invoice_by_id(self.make_invoice(invoice_number=" CUSTOM-9 "))["invoice_number"]
        self.assertEqual(custom, "CUSTOM-9")
        self.assertEqual(inv_db.generate_next_invoice_number(), f"INV-{year}-003")

    def test_snapshots_survive_profile_edits(self):
        client_id = self.make_client("Old Name", email="old@example.com")
        inv_id = self.make_invoice(client_id=client_id, client_name="Old Name")
        inv_db.update_client(client_id, "New Name", email="new@example.com")
        inv = inv_db.get_invoice_by_id(inv_id)
        self.assertEqual(inv["client_name_snapshot"], "Old Name")
        self.assertEqual(inv["sender_name_snapshot"], "Stephen Giang")

    def test_update_replaces_items_and_recalculates(self):
        inv_id = self.make_invoice()
        self.assertTrue(inv_db.update_invoice(inv_id, {"items": [{"description": "New", "quantity": 1, "unit_price": 30}], "tax_rate": 50}))
        inv = inv_db.get_invoice_by_id(inv_id)
        self.assertEqual([i["description"] for i in inv["items"]], ["New"])
        self.assertEqual(inv["total_amount"], 45.0)
        self.assertFalse(inv_db.update_invoice(999, {}))

    def test_status_validation(self):
        inv_id = self.make_invoice()
        self.assertFalse(inv_db.update_invoice_status(inv_id, "bogus"))
        self.assertFalse(inv_db.update_invoice_status(999, "paid"))
        self.assertTrue(inv_db.update_invoice_status(inv_id, " PAID "))
        self.assertEqual(inv_db.get_invoice_by_id(inv_id)["status"], "paid")

    def test_duplicate_makes_fresh_draft(self):
        inv_id = self.make_invoice(status="paid", discount_amount=10, tax_rate=5)
        dup_id = inv_db.duplicate_invoice(inv_id)
        dup, orig = inv_db.get_invoice_by_id(dup_id), inv_db.get_invoice_by_id(inv_id)
        self.assertNotEqual(dup["invoice_number"], orig["invoice_number"])
        self.assertEqual(dup["status"], "draft")
        self.assertEqual(dup["total_amount"], orig["total_amount"])
        self.assertEqual(dup["issue_date"], datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d"))
        self.assertIsNone(inv_db.duplicate_invoice(999))

    def test_delete_cascades_items(self):
        inv_id = self.make_invoice()
        self.assertTrue(inv_db.delete_invoice(inv_id))
        with inv_db.get_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM invoice_items").fetchone()[0], 0)
        self.assertFalse(inv_db.delete_invoice(inv_id))


class TestInvoiceQueries(InvoiceDbTestCase):

    def setUp(self):
        super().setUp()
        self.c1 = self.make_client("Alpha LLC")
        self.c2 = self.make_client("Beta Inc")
        self.a = self.make_invoice(self.c1, client_name="Alpha LLC", issue_date="2030-01-05", due_date=future(30), status="sent",
                                   items=[{"description": "a", "quantity": 1, "unit_price": 100}], notes="priority job")
        self.b = self.make_invoice(self.c2, client_name="Beta Inc", issue_date="2030-02-05", due_date=future(30), status="paid",
                                   items=[{"description": "b", "quantity": 1, "unit_price": 200}])
        self.c = self.make_invoice(self.c1, client_name="Alpha LLC", issue_date="2030-03-05", due_date=future(30), status="void",
                                   items=[{"description": "c", "quantity": 1, "unit_price": 400}])

    def ids(self, **kw):
        return [i["id"] for i in inv_db.get_invoices(**kw)]

    def test_filters(self):
        self.assertEqual(len(self.ids()), 3)
        self.assertEqual(self.ids(status="paid"), [self.b])
        self.assertEqual(len(self.ids(status="all")), 3)
        self.assertEqual(sorted(self.ids(client_id=self.c1)), sorted([self.a, self.c]))
        self.assertEqual(self.ids(search="priority"), [self.a])
        self.assertEqual(self.ids(search="beta"), [self.b])
        self.assertEqual(self.ids(start_date="2030-02-01", end_date="2030-02-28"), [self.b])

    def test_sorting_and_unknown_sort_field(self):
        self.assertEqual(self.ids(sort_by="total_amount", sort_order="asc"), [self.a, self.b, self.c])
        self.assertEqual(self.ids(sort_by="total_amount", sort_order="desc"), [self.c, self.b, self.a])
        self.assertEqual(self.ids(sort_by="; DROP TABLE invoices"), [self.c, self.b, self.a])  # falls back to issue_date desc

    def test_past_due_open_invoices_are_flagged_overdue_on_read(self):
        stale = self.make_invoice(self.c1, due_date="2001-01-01", status="sent")
        paid_old = self.make_invoice(self.c1, due_date="2001-01-01", status="paid")
        inv_db.get_invoices()
        self.assertEqual(inv_db.get_invoice_by_id(stale)["status"], "overdue")
        self.assertEqual(inv_db.get_invoice_by_id(paid_old)["status"], "paid")

    def test_summary_totals(self):
        s = inv_db.get_invoices_summary()
        self.assertEqual(s["total_invoiced"], 300.0)  # void excluded
        self.assertEqual(s["outstanding"], 100.0)
        self.assertEqual(s["paid"], 200.0)
        self.assertEqual(s["total_clients"], 2)
        self.assertEqual((s["total_invoices"], s["void_count"]), (3, 1))
        self.assertEqual(inv_db.get_invoices_summary(status="void")["total_invoiced"], 400.0)
        self.assertEqual(inv_db.get_invoices_summary(client_id=self.c2)["total_clients"], 1)


class TestPresetsAndRecurring(InvoiceDbTestCase):

    def setUp(self):
        super().setUp()
        self.client_id = self.make_client("Recurring Co")
        self.items = [{"description": "Monthly retainer", "quantity": 1, "unit_price": 500}]

    def preset(self, **kw):
        args = dict(client_id=self.client_id, preset_name="P", items=self.items, is_recurring=1,
                    recurrence_type="monthly", recurrence_day=15, recurrence_start_date="")
        args.update(kw)
        return inv_db.add_preset(**args)

    def run_on(self, day):
        return inv_db.process_recurring_invoices(target_date=day)

    def test_monthly_generates_once_per_day(self):
        self.preset()
        self.assertEqual(self.run_on("2030-03-14")["created_count"], 0)
        first = self.run_on("2030-03-15")
        self.assertEqual(first["created_count"], 1)
        self.assertEqual(first["invoices"][0]["due_date"], "2030-03-29")
        self.assertEqual(self.run_on("2030-03-15")["created_count"], 0)  # idempotent
        self.assertEqual(self.run_on("2030-04-15")["created_count"], 1)

    def test_monthly_day_clamps_to_month_length(self):
        self.preset(recurrence_day=31)
        self.assertEqual(self.run_on("2030-02-28")["created_count"], 1)

    def test_start_date_blocks_earlier_runs(self):
        self.preset(recurrence_start_date="2030-06-01")
        self.assertEqual(self.run_on("2030-05-15")["created_count"], 0)
        self.assertEqual(self.run_on("2030-06-15")["created_count"], 1)

    def test_weekly_matches_weekday(self):
        self.preset(recurrence_type="weekly", recurrence_day=4)  # Friday
        self.assertEqual(self.run_on("2030-03-14")["created_count"], 0)  # Thursday
        self.assertEqual(self.run_on("2030-03-15")["created_count"], 1)  # Friday

    def test_biweekly_alternates_from_start_date(self):
        self.preset(recurrence_type="biweekly", recurrence_day=4, recurrence_start_date="2030-03-01")  # a Friday
        self.assertEqual(self.run_on("2030-03-08")["created_count"], 0)
        self.assertEqual(self.run_on("2030-03-15")["created_count"], 1)
        self.assertEqual(self.run_on("2030-03-22")["created_count"], 0)
        self.assertEqual(self.run_on("2030-03-29")["created_count"], 1)

    def test_auto_status_discount_and_tax_flow_into_invoice(self):
        self.preset(auto_status="sent", discount_amount=50, tax_rate=10)
        inv_id = self.run_on("2030-03-15")["invoices"][0]["id"]
        inv = inv_db.get_invoice_by_id(inv_id)
        self.assertEqual(inv["status"], "sent")
        self.assertEqual(inv["total_amount"], 495.0)

    def test_non_recurring_and_orphaned_presets_are_skipped(self):
        self.preset(is_recurring=0)
        self.assertEqual(self.run_on("2030-03-15")["created_count"], 0)
        self.assertEqual(inv_db.get_recurring_presets(), [])

    def test_bad_date_string_falls_back_to_today(self):
        self.assertEqual(inv_db.process_recurring_invoices(target_date="not-a-date")["date"], datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d"))

    def test_preset_crud_and_cascade_with_client(self):
        pid = self.preset(is_recurring=0)
        self.assertEqual(inv_db.get_preset_by_id(pid)["preset_name"], "P")
        self.assertTrue(inv_db.update_preset(pid, "Renamed", items=self.items, is_recurring=1))
        self.assertEqual(len(inv_db.get_recurring_presets()), 1)
        self.assertEqual(len(inv_db.get_all_presets()), 1)
        self.assertEqual(len(inv_db.get_presets_by_client(self.client_id)), 1)
        self.assertTrue(inv_db.delete_client(self.client_id))
        self.assertEqual(inv_db.get_all_presets(), [])
        self.assertFalse(inv_db.delete_preset(pid))


class TestInvoiceRoutes(InvoiceDbTestCase):

    def setUp(self):
        super().setUp()
        app = Flask(__name__, template_folder=TEMPLATE_DIR)
        app.config["TESTING"] = True
        app.register_blueprint(invoice_bp)
        self.client = app.test_client()

    def create_invoice(self, **extra):
        body = {"client_name": "Route Client", "items": [{"description": "Work", "quantity": 1, "unit_price": 80}]}
        body.update(extra)
        resp = self.client.post("/api/invoices", json=body)
        self.assertEqual(resp.status_code, 201)
        return resp.get_json()["invoice_id"]

    def test_pages(self):
        self.assertEqual(self.client.get("/invoices").status_code, 200)
        inv_id = self.create_invoice()
        preview = self.client.get(f"/invoices/{inv_id}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertIn(b"Route Client", preview.data)
        self.assertEqual(self.client.get("/invoices/999/preview").status_code, 404)

    def test_sender_endpoints(self):
        self.assertEqual(self.client.post("/api/invoices/senders", json={}).status_code, 400)
        sid = self.client.post("/api/invoices/senders", json={"name": "Biz", "phone": "6195551234"}).get_json()["sender_id"]
        self.assertEqual(self.client.get(f"/api/invoices/senders/{sid}").get_json()["phone"], "+1 (619) 555-1234")
        self.assertEqual(self.client.get("/api/invoices/senders/999").status_code, 404)
        self.assertEqual(self.client.put(f"/api/invoices/senders/{sid}", json={"name": ""}).status_code, 400)
        self.assertTrue(self.client.put(f"/api/invoices/senders/{sid}", json={"name": "Biz 2"}).get_json()["success"])
        self.assertEqual(self.client.put("/api/invoices/senders/999", json={"name": "x"}).status_code, 404)
        self.assertEqual(self.client.patch(f"/api/invoices/senders/{sid}/default").status_code, 200)
        self.assertEqual(self.client.patch("/api/invoices/senders/999/default").status_code, 404)
        defaults = [s for s in self.client.get("/api/invoices/senders").get_json() if s["is_default"]]
        self.assertEqual([s["id"] for s in defaults], [sid])
        self.assertEqual(self.client.delete(f"/api/invoices/senders/{sid}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/invoices/senders/{sid}").status_code, 404)

    def test_client_endpoints(self):
        self.assertEqual(self.client.post("/api/invoices/clients", json={"name": " "}).status_code, 400)
        cid = self.client.post("/api/invoices/clients", json={"name": "Cli", "email": "c@example.com"}).get_json()["client_id"]
        self.assertEqual(self.client.get(f"/api/invoices/clients/{cid}").get_json()["email"], "c@example.com")
        self.assertEqual(self.client.get("/api/invoices/clients/999").status_code, 404)
        self.assertEqual(self.client.put(f"/api/invoices/clients/{cid}", json={}).status_code, 400)
        self.assertEqual(self.client.put("/api/invoices/clients/999", json={"name": "x"}).status_code, 404)
        self.assertTrue(self.client.put(f"/api/invoices/clients/{cid}", json={"name": "Cli 2"}).get_json()["success"])
        self.assertEqual([c["name"] for c in self.client.get("/api/invoices/clients").get_json()], ["Cli 2"])
        self.assertEqual(self.client.delete(f"/api/invoices/clients/{cid}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/invoices/clients/{cid}").status_code, 404)

    def test_preset_endpoints(self):
        cid = self.client.post("/api/invoices/clients", json={"name": "P Client"}).get_json()["client_id"]
        self.assertEqual(self.client.post("/api/invoices/presets", json={"client_id": cid}).status_code, 400)
        body = {"client_id": cid, "preset_name": "Retainer", "items": [{"description": "x", "quantity": 1, "unit_price": 1}],
                "is_recurring": True, "recurrence_type": "weekly", "recurrence_day": 2}
        pid = self.client.post("/api/invoices/presets", json=body).get_json()["preset_id"]
        self.assertEqual(self.client.get(f"/api/invoices/presets/{cid}").get_json()[0]["preset_name"], "Retainer")
        self.assertEqual(len(self.client.get("/api/invoices/presets").get_json()), 1)
        self.assertEqual(self.client.get(f"/api/invoices/presets/detail/{pid}").get_json()["recurrence_type"], "weekly")
        self.assertEqual(self.client.get("/api/invoices/presets/detail/999").status_code, 404)
        self.assertEqual(self.client.put(f"/api/invoices/presets/{pid}", json={}).status_code, 400)
        self.assertEqual(self.client.put("/api/invoices/presets/999", json={"preset_name": "x"}).status_code, 404)
        self.assertTrue(self.client.put(f"/api/invoices/presets/{pid}", json={"preset_name": "Renamed", "is_recurring": True}).get_json()["success"])
        self.assertEqual(self.client.get("/api/invoices/recurring").get_json()[0]["preset_name"], "Renamed")
        self.assertEqual(self.client.delete(f"/api/invoices/presets/{pid}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/invoices/presets/{pid}").status_code, 404)

    def test_recurring_run_accepts_get_post_query_and_body(self):
        for call in (lambda: self.client.get("/api/invoices/recurring/run?date=2030-01-01"),
                     lambda: self.client.post("/api/invoices/recurring/run?date=2030-01-01"),
                     lambda: self.client.post("/api/invoices/recurring/run", json={"date": "2030-01-01"})):
            self.assertEqual(call().get_json()["date"], "2030-01-01")

    def test_invoice_lifecycle_endpoints(self):
        inv_id = self.create_invoice(discount_amount=10)
        fetched = self.client.get(f"/api/invoices/{inv_id}").get_json()
        self.assertEqual(fetched["total_amount"], 70.0)
        self.assertEqual(self.client.get("/api/invoices/999").status_code, 404)

        self.assertTrue(self.client.put(f"/api/invoices/{inv_id}", json={"discount_amount": 0, "items": [{"description": "Changed", "quantity": 1, "unit_price": 30}]}).get_json()["success"])
        self.assertEqual(self.client.put("/api/invoices/999", json={}).status_code, 404)

        self.assertEqual(self.client.patch(f"/api/invoices/{inv_id}/status", json={}).status_code, 400)
        self.assertEqual(self.client.patch(f"/api/invoices/{inv_id}/status", json={"status": "nope"}).status_code, 400)
        self.assertEqual(self.client.patch(f"/api/invoices/{inv_id}/status", json={"status": "paid"}).status_code, 200)

        dup = self.client.post(f"/api/invoices/{inv_id}/duplicate")
        self.assertEqual(dup.status_code, 201)
        self.assertNotEqual(dup.get_json()["invoice_number"], fetched["invoice_number"])
        self.assertEqual(self.client.post("/api/invoices/999/duplicate").status_code, 404)

        listed = self.client.get("/api/invoices?status=paid&sort_by=total_amount&sort_order=asc").get_json()
        self.assertEqual([i["id"] for i in listed], [inv_id])
        summary = self.client.get("/api/invoices/summary?status=paid").get_json()
        self.assertEqual(summary["paid"], 30.0)
        self.assertTrue(self.client.get("/api/invoices/next-number").get_json()["next_number"].startswith("INV-"))

        self.assertEqual(self.client.delete(f"/api/invoices/{inv_id}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/invoices/{inv_id}").status_code, 404)

    def test_create_invoice_error_returns_400(self):
        with patch("modules.InvoiceGenerator.routes.create_invoice", side_effect=RuntimeError("bad data")):
            resp = self.client.post("/api/invoices", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "bad data")

    def test_pdf_download(self):
        inv_id = self.create_invoice(client_name="Fancy / Client: #1")
        resp = self.client.get(f"/api/invoices/{inv_id}/pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/pdf")
        self.assertTrue(resp.data.startswith(b"%PDF"))
        disposition = resp.headers["Content-Disposition"]
        self.assertIn("attachment", disposition)
        self.assertNotIn("/", disposition.split("filename=")[1])
        self.assertEqual(self.client.get("/api/invoices/999/pdf").status_code, 404)


class TestPdfContent(unittest.TestCase):

    def pdf(self, **overrides):
        from modules.InvoiceGenerator.pdf import generate_invoice_pdf
        invoice = {
            "invoice_number": "INV-1", "client_name_snapshot": "Client", "sender_name_snapshot": "Sender",
            "sender_info": {}, "client_info": {}, "issue_date": "2030-01-01", "due_date": "2030-01-15", "status": "sent",
            "subtotal": 10.0, "discount_amount": 0.0, "tax_rate": 0.0, "total_amount": 10.0,
            "items": [{"description": "x", "quantity": 1, "unit_price": 10.0, "amount": 10.0}],
        }
        invoice.update(overrides)
        buf = generate_invoice_pdf(invoice)
        self.assertEqual(buf.tell(), 0)
        return buf.getvalue()

    def test_renders_with_many_items_discount_and_tax(self):
        items = [{"description": f"Line {i}", "quantity": 1, "unit_price": 1.0, "amount": 1.0} for i in range(80)]
        data = self.pdf(items=items, discount_amount=5.0, tax_rate=8.5, tax_amount=0.68, status="paid")
        self.assertTrue(data.startswith(b"%PDF"))

    def test_renders_with_missing_optional_fields(self):
        self.assertTrue(self.pdf(items=[], notes=None, payment_instructions=None).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
