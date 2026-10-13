"""HTTP-level tests for the TutoringCalculator blueprint. Google, Gmail and Twilio are mocked."""
import datetime
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from flask import Flask

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.TutoringCalculator import routes
from modules.TutoringCalculator.config import PST

R = "modules.TutoringCalculator.routes"


def freeze_today(year, month, day):
    """Patches routes.datetime so calculate_billing_dates sees a fixed date."""
    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return PST.localize(datetime.datetime(year, month, day, 9, 0))
    return patch(f"{R}.datetime", SimpleNamespace(datetime=FixedDateTime, timedelta=datetime.timedelta))


class TutoringRouteTestCase(unittest.TestCase):

    def setUp(self):
        routes._YEAR_FOLDER_CACHE.clear()
        app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "index"))
        app.config["TESTING"] = True
        app.register_blueprint(routes.tutoring_bp)
        self.client = app.test_client()
        self.creds = MagicMock(valid=True)
        self.creds_patch = patch(f"{R}.get_credentials", return_value=self.creds)
        self.get_credentials = self.creds_patch.start()
        self.folder_patch = patch(f"{R}.resolve_year_folder_url", return_value="https://drive/year")
        self.folder_patch.start()

    def tearDown(self):
        self.creds_patch.stop()
        self.folder_patch.stop()

    def logged_out(self):
        self.get_credentials.return_value = None


class TestBillingDates(unittest.TestCase):

    def test_midweek_uses_the_most_recent_monday(self):
        # The calculator is meant to run on Monday; any other weekday returns the week that started most recently.
        with freeze_today(2026, 10, 14):  # Wednesday
            dates = routes.calculate_billing_dates()
        self.assertEqual((dates["start_date"], dates["end_date"]), ("10.12.26", "10.18.26"))
        self.assertEqual((dates["start_date_full"], dates["end_date_full"]), ("2026-10-12", "2026-10-18"))

    def test_on_monday_uses_the_week_that_just_ended(self):
        with freeze_today(2026, 10, 12):  # Monday
            self.assertEqual(routes.calculate_billing_dates()["start_date"], "10.05.26")

    def test_on_sunday_uses_the_week_ending_today(self):
        with freeze_today(2026, 10, 11):  # Sunday
            self.assertEqual(routes.calculate_billing_dates()["start_date"], "10.05.26")

    def test_week_spanning_new_year(self):
        with freeze_today(2026, 1, 7):  # Wednesday
            dates = routes.calculate_billing_dates()
        self.assertEqual((dates["start_date"], dates["end_date"]), ("01.05.26", "01.11.26"))


class TestPagesAndOAuth(TutoringRouteTestCase):

    def test_privacy_page_is_public_html(self):
        resp = self.client.get("/privacy")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"<html", resp.data.lower())

    def test_dashboard_renders_for_both_auth_states(self):
        for path in ("/tutoring", "/tutoring/dashboard"):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.logged_out()
        self.assertEqual(self.client.get("/tutoring").status_code, 200)

    def test_login_redirects_to_google(self):
        with patch(f"{R}.initiate_oauth_flow", return_value="https://accounts.google.com/auth") as start:
            resp = self.client.get("/login_oauth")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], "https://accounts.google.com/auth")
        self.assertEqual(start.call_args.kwargs["state"], "swagger")

    def test_login_start_failure_is_500(self):
        with patch(f"{R}.initiate_oauth_flow", side_effect=RuntimeError("no client file")):
            resp = self.client.get("/login_oauth")
        self.assertEqual(resp.status_code, 500)
        self.assertIn("no client file", resp.get_json()["message"])

    def test_callback_success_redirects_to_dashboard(self):
        with patch(f"{R}.process_oauth_callback") as callback:
            resp = self.client.get("/login_oauth?code=abc&state=swagger")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/tutoring", resp.headers["Location"])
        callback.assert_called_once()

    def test_callback_failure_is_400(self):
        with patch(f"{R}.process_oauth_callback", side_effect=ValueError("bad code")):
            resp = self.client.get("/login_oauth?code=abc")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("bad code", resp.get_json()["message"])


class TestYearFolderLookup(unittest.TestCase):

    def setUp(self):
        routes._YEAR_FOLDER_CACHE.clear()

    def test_resolves_and_caches(self):
        with patch(f"{R}.get_drive_service"), patch(f"{R}.get_or_create_year_folder", return_value="abc") as lookup:
            first = routes.resolve_year_folder_url(MagicMock(valid=True), "2026")
            second = routes.resolve_year_folder_url(MagicMock(valid=True), "2026")
        self.assertEqual(first, "https://drive.google.com/drive/folders/abc")
        self.assertEqual(second, first)
        lookup.assert_called_once()

    def test_returns_none_without_valid_credentials_or_on_error(self):
        self.assertIsNone(routes.resolve_year_folder_url(None, "2026"))
        self.assertIsNone(routes.resolve_year_folder_url(MagicMock(valid=False), "2026"))
        with patch(f"{R}.get_drive_service", side_effect=RuntimeError("drive down")):
            self.assertIsNone(routes.resolve_year_folder_url(MagicMock(valid=True), "2026"))


class TestStatus(TutoringRouteTestCase):

    def sheets(self, *names):
        return [{"id": f"id{i}", "name": n} for i, n in enumerate(names)]

    def test_logged_out_reports_auth_url(self):
        self.logged_out()
        data = self.client.get("/api/tutoring/status").get_json()
        self.assertFalse(data["is_authenticated"])
        self.assertIn("login_oauth", data["auth_url"])
        self.assertEqual(data["current_sheets"], [])

    def test_sheet_lookup_is_opt_in(self):
        with patch(f"{R}.find_current_week_sheets") as find:
            data = self.client.get("/api/tutoring/status").get_json()
        find.assert_not_called()
        self.assertTrue(data["is_authenticated"])
        self.assertIsNone(data["auth_url"])
        self.assertEqual(data["year_folder_url"], "https://drive/year")

    def test_single_sheet_pending_review(self):
        with patch(f"{R}.find_current_week_sheets", return_value=self.sheets("10.05.26 - 10.11.26 CALCULATED")):
            data = self.client.get("/api/tutoring/status?check_sheet=1").get_json()
        self.assertFalse(data["has_multiple_sheets"])
        self.assertTrue(data["current_sheet"]["is_pending_review"])
        self.assertEqual(data["current_sheet"]["status_label"], "Pending Review (CALCULATED)")

    def test_single_approved_sheet(self):
        with patch(f"{R}.find_current_week_sheets", return_value=self.sheets("10.05.26 - 10.11.26")):
            data = self.client.get("/api/tutoring/status?check_sheet=1").get_json()
        self.assertEqual(data["current_sheet"]["status_label"], "Approved")
        self.assertTrue(data["current_sheet"]["sheet_url"].endswith("/id0/edit"))

    def test_multiple_sheets_flagged(self):
        with patch(f"{R}.find_current_week_sheets", return_value=self.sheets("a", "b")):
            data = self.client.get("/api/tutoring/status?check_sheet=1").get_json()
        self.assertTrue(data["has_multiple_sheets"])
        self.assertEqual(len(data["current_sheets"]), 2)

    def test_lookup_error_is_returned_in_payload(self):
        with patch(f"{R}.find_current_week_sheets", side_effect=RuntimeError("drive down")):
            resp = self.client.get("/api/tutoring/status?check_sheet=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["current_sheet"], {"error": "drive down"})

    def test_legacy_aliases_still_work(self):
        for path in ("/api/status", "/tutoring/status"):
            self.assertEqual(self.client.get(path).status_code, 200, path)


class TestRunCalc(TutoringRouteTestCase):

    COPY = {"status": "success", "sheet_id": "S1", "sheet_url": "https://sheet", "title": "10.05.26 - 10.11.26 CALCULATED", "year_folder_id": "Y1"}
    UPDATE = {"updated_students": [{"name": "Elijah Dinh"}], "total_balance": "$120.00"}

    def patches(self, copy=None, email=None):
        return (patch(f"{R}.copy_template_sheet", return_value=copy or self.COPY),
                patch("modules.TutoringCalculator.apis.drive_sheets_api.get_student_names_from_sheet", return_value=["Elijah Dinh"]),
                patch(f"{R}.calculate_tutoring_hours", return_value={"Elijah Dinh": 2.0}),
                patch(f"{R}.fetch_previous_balances", return_value={}),
                patch(f"{R}.update_sheet_hours_and_balances", return_value=self.UPDATE),
                patch(f"{R}.send_calculation_email", return_value=email or {"status": "success", "email_id": "m1"}))

    def run_with(self, *, url="/api/tutoring/run-calc", copy=None, email=None, **request):
        copy_p, names_p, hours_p, prev_p, upd_p, email_p = self.patches(copy, email)
        with copy_p as copy_m, names_p, hours_p as hours_m, prev_p, upd_p, email_p as email_m:
            resp = self.client.post(url, **request)
        return resp, copy_m, hours_m, email_m

    def test_requires_google_login(self):
        self.logged_out()
        resp = self.client.post("/api/tutoring/run-calc")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["status"], "unauthenticated")

    def test_success_with_default_dates_and_email(self):
        with freeze_today(2026, 10, 12):
            resp, copy_m, hours_m, email_m = self.run_with()
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(copy_m.call_args.args[1:], ("10.05.26", "10.11.26"))
        self.assertEqual(data["students_count"], 1)
        self.assertEqual(data["total_balance"], "$120.00")
        self.assertEqual(data["hours_breakdown"], {"Elijah Dinh": 2.0})
        self.assertEqual(data["email_status"], "success")
        self.assertIn("Email notification sent", data["message"])
        self.assertEqual(data["year_folder_url"], "https://drive.google.com/drive/folders/Y1")
        email_m.assert_called_once()

    def test_explicit_dates_from_query_or_body(self):
        resp, copy_m, *_ = self.run_with(query_string={"start_date": "09.01.26", "end_date": "09.07.26"})
        self.assertEqual(copy_m.call_args.args[1:], ("09.01.26", "09.07.26"))
        resp, copy_m, *_ = self.run_with(json={"start_date": "08.03.26", "end_date": "08.09.26"})
        self.assertEqual(copy_m.call_args.args[1:], ("08.03.26", "08.09.26"))

    def test_send_email_flag_parsing(self):
        for raw in ("false", "0", "no", "off", "None"):
            resp, _, _, email_m = self.run_with(query_string={"send_email": raw})
            email_m.assert_not_called()
            self.assertEqual(resp.get_json()["email_status"], "skipped", raw)
            self.assertIn("Email skipped", resp.get_json()["message"])
        resp, _, _, email_m = self.run_with(json={"send_email": False})
        email_m.assert_not_called()
        resp, _, _, email_m = self.run_with(query_string={"send_email": "true"})
        email_m.assert_called_once()

    def test_email_failure_is_reported_but_run_still_succeeds(self):
        resp, *_ = self.run_with(email={"status": "error", "message": "gmail down"})
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["email_error"], "gmail down")
        self.assertNotIn("Email notification sent", data["message"])

    def test_missing_year_folder_is_looked_up_for_the_email(self):
        copy = dict(self.COPY, year_folder_id=None)
        copy_p, names_p, hours_p, prev_p, upd_p, email_p = self.patches(copy)
        with copy_p, names_p, hours_p, prev_p, upd_p, email_p as email_m, \
             patch(f"{R}.get_sheet_details", return_value={"parents": ["P9"]}):
            self.client.post("/api/tutoring/run-calc")
        self.assertEqual(email_m.call_args.kwargs["year_folder_id"], "P9")

    def test_already_approved_sheet_short_circuits(self):
        copy = {"status": "already_approved", "already_approved": True, "sheet_id": "A1", "sheet_url": "u", "title": "t", "year_folder_id": "Y1"}
        resp, _, hours_m, email_m = self.run_with(copy=copy)
        data = resp.get_json()
        self.assertEqual((resp.status_code, data["status"], data["email_status"]), (200, "skipped", "skipped"))
        hours_m.assert_not_called()
        email_m.assert_not_called()

    def test_failure_returns_500(self):
        with patch(f"{R}.copy_template_sheet", side_effect=RuntimeError("drive quota")):
            resp = self.client.post("/api/tutoring/run-calc")
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.get_json(), {"status": "error", "message": "drive quota"})

    def test_legacy_urls(self):
        for url in ("/api/run-calc", "/tutoring/run-calc", "/run-calc"):
            resp, *_ = self.run_with(url=url)
            self.assertEqual(resp.status_code, 200, url)


class TestSendTexts(TutoringRouteTestCase):

    def post(self, **kw):
        return self.client.post("/api/tutoring/send-texts", **kw)

    def test_requires_google_login(self):
        self.logged_out()
        self.assertEqual(self.post().status_code, 401)

    def test_no_sheet_for_week_is_404(self):
        with patch(f"{R}.find_current_week_sheets", return_value=[]):
            resp = self.post()
        self.assertEqual(resp.status_code, 404)
        self.assertIn("run calculations first", resp.get_json()["message"])

    def test_duplicate_sheets_block_sending(self):
        files = [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]
        with patch(f"{R}.find_current_week_sheets", return_value=files), patch(f"{R}.send_sms") as sms:
            resp = self.post()
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(resp.get_json()["has_multiple_sheets"])
        sms.assert_not_called()

    def test_calculated_title_blocks_sending(self):
        pending = {"is_pending_review": True, "title": "10.05.26 - 10.11.26 CALCULATED", "message": "review first", "recipients": []}
        with patch(f"{R}.get_pending_text_recipients", return_value=pending), patch(f"{R}.send_sms") as sms, \
             patch(f"{R}.update_sheet_pay_status") as pay:
            resp = self.post(json={"sheet_id": "S1"})
        data = resp.get_json()
        self.assertEqual((resp.status_code, data["status"], data["is_pending_review"]), (200, "skipped", True))
        sms.assert_not_called()
        pay.assert_not_called()

    def test_nobody_to_text(self):
        with patch(f"{R}.get_pending_text_recipients", return_value={"is_pending_review": False, "title": "t", "recipients": []}), \
             patch(f"{R}.read_text_logs", return_value="logs"), patch(f"{R}.send_sms") as sms:
            data = self.post(query_string={"sheet_id": "S1"}).get_json()
        self.assertEqual((data["sent_count"], data["recent_logs"]), (0, "logs"))
        sms.assert_not_called()

    def test_texts_are_sent_and_status_updated(self):
        recipients = [{"student": "Elijah Dinh", "phone": "6195551234", "text": "Pay $120"},
                      {"student": "Ellie Hoang", "phone": "6195559999", "text": "Pay $60"}]
        pending = {"is_pending_review": False, "title": "10.05.26 - 10.11.26", "recipients": recipients}
        with patch(f"{R}.find_current_week_sheets", return_value=[{"id": "S9", "name": "n"}]), \
             patch(f"{R}.get_pending_text_recipients", return_value=pending) as get_pending, \
             patch(f"{R}.send_sms", return_value={"status": "sent"}) as sms, \
             patch(f"{R}.update_sheet_pay_status") as pay, patch(f"{R}.read_text_logs", return_value="log"):
            data = self.post().get_json()
        get_pending.assert_called_once_with(self.creds, "S9")
        self.assertEqual(data["sent_count"], 2)
        self.assertEqual(sms.call_args_list[0].kwargs, {"to_phone": "6195551234", "message_body": "Pay $120", "student_name": "Elijah Dinh"})
        pay.assert_called_once_with(self.creds, "S9")
        self.assertIn("2 text message reminders", data["message"])

    def test_single_text_message_is_not_pluralized(self):
        pending = {"is_pending_review": False, "title": "t", "recipients": [{"student": "A", "phone": "1", "text": "x"}]}
        with patch(f"{R}.get_pending_text_recipients", return_value=pending), patch(f"{R}.send_sms", return_value={}), \
             patch(f"{R}.update_sheet_pay_status"), patch(f"{R}.read_text_logs", return_value=""):
            data = self.post(json={"sheet_id": "S1"}).get_json()
        self.assertIn("1 text message reminder.", data["message"])

    def test_unexpected_error_is_500(self):
        with patch(f"{R}.get_pending_text_recipients", side_effect=RuntimeError("sheets down")):
            resp = self.post(json={"sheet_id": "S1"})
        self.assertEqual(resp.status_code, 500)


class TestStepwiseEndpoints(TutoringRouteTestCase):

    def test_dates(self):
        with freeze_today(2026, 10, 12):
            self.assertEqual(self.client.get("/api/tutoring/dates").get_json()["start_date"], "10.05.26")

    def test_text_logs_are_plain_text(self):
        with patch(f"{R}.read_text_logs", return_value="line"):
            resp = self.client.get("/api/tutoring/text-logs")
        self.assertEqual((resp.mimetype, resp.data), ("text/plain", b"line"))

    def test_copy_template(self):
        with patch(f"{R}.copy_template_sheet", return_value={"status": "success"}) as copy:
            resp = self.client.post("/api/tutoring/copy-template", json={"start_date": "10.05.26", "end_date": "10.11.26"})
        self.assertEqual(resp.get_json(), {"status": "success"})
        self.assertEqual(copy.call_args.args[1:], ("10.05.26", "10.11.26"))
        with patch(f"{R}.copy_template_sheet", side_effect=RuntimeError("x")):
            self.assertEqual(self.client.post("/api/tutoring/copy-template").status_code, 500)
        self.logged_out()
        self.assertEqual(self.client.post("/api/tutoring/copy-template").status_code, 401)

    def test_calc_hours(self):
        with patch(f"{R}.calculate_tutoring_hours", return_value={"Elijah": 2.0}) as calc:
            resp = self.client.get("/api/tutoring/calc-hours?start_date=10.05.26&end_date=10.11.26")
        self.assertEqual(resp.get_json(), {"Elijah": 2.0})
        self.assertEqual(calc.call_args.args[1:], ("10.05.26", "10.11.26"))
        with patch(f"{R}.calculate_tutoring_hours", side_effect=RuntimeError("cal down")):
            self.assertEqual(self.client.get("/api/tutoring/calc-hours").status_code, 500)
        self.logged_out()
        self.assertEqual(self.client.get("/api/tutoring/calc-hours").status_code, 401)

    def test_previous_balances(self):
        with patch(f"{R}.fetch_previous_balances", return_value={"Elijah": 60.0}) as prev:
            resp = self.client.get("/api/tutoring/previous-balances?start_date=10.05.26&end_date=10.11.26")
        self.assertEqual(resp.get_json(), {"Elijah": 60.0})
        self.assertEqual(prev.call_args.args[1:], ("10.05.26", "10.11.26"))
        with freeze_today(2026, 10, 12), patch(f"{R}.fetch_previous_balances", return_value={}) as prev:
            self.client.get("/api/tutoring/previous-balances")
        self.assertEqual(prev.call_args.args[1:], ("10.05.26", "10.11.26"))
        with patch(f"{R}.fetch_previous_balances", side_effect=RuntimeError("x")):
            self.assertEqual(self.client.get("/api/tutoring/previous-balances").status_code, 500)


class TestUpdateSheet(TutoringRouteTestCase):

    URL = "/api/tutoring/update-sheet"

    def test_requires_login_and_parameters(self):
        self.assertEqual(self.client.post(self.URL, json={"sheet_id": "S"}).status_code, 400)
        self.assertEqual(self.client.post(self.URL, json={"action": "update_hours"}).status_code, 400)
        self.logged_out()
        self.assertEqual(self.client.post(self.URL, json={"sheet_id": "S", "action": "update_hours"}).status_code, 401)

    def test_unknown_action(self):
        resp = self.client.post(self.URL, json={"sheet_id": "S", "action": "explode"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unknown action", resp.get_json()["message"])

    def test_update_pay_status(self):
        with patch(f"{R}.update_sheet_pay_status", return_value={"status": "success", "updated_count": 2}) as pay:
            resp = self.client.post(self.URL, json={"sheet_id": "S", "action": "update_pay_status"})
        self.assertEqual(resp.get_json()["action"], "update_pay_status")
        pay.assert_called_once_with(self.creds, "S")
        with patch(f"{R}.update_sheet_pay_status", side_effect=RuntimeError("x")):
            self.assertEqual(self.client.post(self.URL, json={"sheet_id": "S", "action": "update_pay_status"}).status_code, 500)

    def test_update_hours_with_explicit_dates_and_email(self):
        result = {"status": "success", "sheet_url": "u", "updated_students": [], "total_balance": "$0"}
        with patch(f"{R}.calculate_tutoring_hours", return_value={}) as calc, patch(f"{R}.fetch_previous_balances", return_value={}), \
             patch(f"{R}.update_sheet_hours_and_balances", return_value=dict(result)), \
             patch(f"{R}.get_sheet_details", return_value={"parents": ["Y1"]}), patch(f"{R}.send_calculation_email") as email:
            resp = self.client.post(self.URL, json={"sheet_id": "S", "action": "update_hours", "start_date": "10.05.26", "end_date": "10.11.26"})
        data = resp.get_json()
        self.assertEqual((data["action"], data["send_email"]), ("update_hours", True))
        self.assertEqual(calc.call_args.args[1:], ("10.05.26", "10.11.26"))
        self.assertEqual(email.call_args.kwargs["year_folder_id"], "Y1")

    def test_update_hours_without_email_reads_dates_from_sheet(self):
        sheets = MagicMock()
        sheets.spreadsheets().values().get().execute.return_value = {"values": [["10.05.26", "10.11.26"]]}
        with patch("modules.TutoringCalculator.apis.drive_sheets_api.get_sheets_service", return_value=sheets), \
             patch(f"{R}.calculate_tutoring_hours", return_value={}) as calc, patch(f"{R}.fetch_previous_balances", return_value={}), \
             patch(f"{R}.update_sheet_hours_and_balances", return_value={"status": "success"}), patch(f"{R}.send_calculation_email") as email:
            resp = self.client.post(self.URL + "?send_email=false", json={"sheet_id": "S", "action": "update_hours"})
        self.assertEqual(calc.call_args.args[1:], ("10.05.26", "10.11.26"))
        email.assert_not_called()
        self.assertFalse(resp.get_json()["send_email"])

    def test_update_hours_failure(self):
        with patch(f"{R}.calculate_tutoring_hours", side_effect=RuntimeError("cal down")):
            resp = self.client.post(self.URL, json={"sheet_id": "S", "action": "update_hours", "start_date": "a", "end_date": "b"})
        self.assertEqual(resp.status_code, 500)


if __name__ == "__main__":
    unittest.main()
