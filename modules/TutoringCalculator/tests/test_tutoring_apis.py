"""Unit tests for the TutoringCalculator config and API helper modules. Every Google/Twilio call is mocked."""
import base64
import datetime
import json
import os
import pickle
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, mock_open, patch

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from googleapiclient.errors import HttpError

from modules.TutoringCalculator import config as tutoring_config
from modules.TutoringCalculator.apis import calendar_api, drive_sheets_api, email_api, google_auth, twilio_api

DRIVE = "modules.TutoringCalculator.apis.drive_sheets_api"


class TestConfig(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config_dir = os.path.join(self.tmp.name, "config")
        os.makedirs(self.config_dir)
        self.patches = [patch.object(tutoring_config, "CONFIG_DIR", self.config_dir),
                        patch.object(tutoring_config, "BASE_DIR", self.tmp.name)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def write(self, folder, name, data):
        with open(os.path.join(folder, name), "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))

    def test_values_come_from_config_and_secrets(self):
        self.write(self.config_dir, "config.json", {
            "GOOGLE_CALENDAR_ID": "cal", "PAY_PARENT_FOLDER_ID": "folder", "TEMPLATE_SHEET_ID": "tmpl",
            "NOTIFICATION_EMAIL": "me@example.com", "APP_HOST": "https://host", "TWILIO_FROM_NUMBER": "+15550001111",
            "TWILIO_ACCOUNT_SID": "AC1", "TWILIO_API_KEY_SID": "SK1"})
        self.write(self.config_dir, "secrets.json", {"TWILIO_API_SECRET": "shh"})
        self.assertEqual(tutoring_config.GOOGLE_CALENDAR_ID, "cal")
        self.assertEqual(tutoring_config.PAY_PARENT_FOLDER_ID, "folder")
        self.assertEqual(tutoring_config.TEMPLATE_SHEET_ID, "tmpl")
        self.assertEqual(tutoring_config.NOTIFICATION_EMAIL, "me@example.com")
        self.assertEqual(tutoring_config.APP_HOST, "https://host")
        self.assertEqual(tutoring_config.TWILIO_ACCOUNT_SID, "AC1")
        self.assertEqual(tutoring_config.TWILIO_API_KEY_SID, "SK1")
        self.assertEqual(tutoring_config.TWILIO_FROM_NUMBER, "+15550001111")
        self.assertEqual(tutoring_config.TWILIO_API_SECRET, "shh")
        self.assertEqual(tutoring_config.CONFIG["APP_HOST"], "https://host")
        self.assertEqual(tutoring_config.SECRETS, {"TWILIO_API_SECRET": "shh"})

    def test_config_is_reread_on_every_access(self):
        self.write(self.config_dir, "config.json", {"APP_HOST": "one"})
        self.assertEqual(tutoring_config.APP_HOST, "one")
        self.write(self.config_dir, "config.json", {"APP_HOST": "two"})
        self.assertEqual(tutoring_config.APP_HOST, "two")

    def test_missing_or_broken_files_give_empty_config(self):
        self.assertEqual(tutoring_config.CONFIG, {})
        self.assertIsNone(tutoring_config.APP_HOST)
        self.write(self.config_dir, "config.json", "{not json")
        self.assertEqual(tutoring_config.CONFIG, {})

    def test_falls_back_to_base_dir(self):
        self.write(self.tmp.name, "config.json", {"APP_HOST": "from-base"})
        self.assertEqual(tutoring_config.APP_HOST, "from-base")

    def test_oauth_file_resolution(self):
        self.assertIsNone(tutoring_config.OAUTH_FILE)
        self.write(self.config_dir, "config.json", {"OAUTH_FILE": "client.json"})
        self.assertEqual(tutoring_config.OAUTH_FILE, os.path.join(self.config_dir, "client.json"))  # not created yet
        self.write(self.tmp.name, "client.json", "{}")
        self.assertEqual(tutoring_config.OAUTH_FILE, os.path.join(self.tmp.name, "client.json"))
        self.write(self.config_dir, "client.json", "{}")
        self.assertEqual(tutoring_config.OAUTH_FILE, os.path.join(self.config_dir, "client.json"))  # config dir wins

    def test_derived_paths_and_unknown_attribute(self):
        self.assertTrue(tutoring_config.TOKEN_PICKLE_FILE.endswith(os.path.join("keys", "token.pickle")))
        self.assertTrue(tutoring_config.TEXT_LOG_FILE.endswith(os.path.join("logs", "text_messages.log")))
        with self.assertRaises(AttributeError):
            tutoring_config.DOES_NOT_EXIST


class TestTwilio(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.tmp.name, "text_messages.log")
        self.patch = patch.object(twilio_api, "TEXT_LOG_FILE", self.log)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def read_log(self):
        with open(self.log) as f:
            return f.read()

    def response(self, status, payload):
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = payload
        resp.text = json.dumps(payload)
        return resp

    def test_e164_formatting(self):
        cases = {"(619) 555-1234": "+16195551234", "619-555-1234": "+16195551234", "1 619 555 1234": "+16195551234",
                 "+44 20 7946 0958": "+442079460958", "447911123456": "+447911123456", "555": "555"}
        for raw, expected in cases.items():
            self.assertEqual(twilio_api.format_phone_e164(raw), expected, raw)

    def test_send_success_is_logged(self):
        with patch.object(twilio_api.requests, "post", return_value=self.response(201, {"sid": "SM123"})) as post:
            result = twilio_api.send_sms("(619) 555-1234", "Pay up", "Elijah")
        self.assertEqual(result, {"status": "sent", "phone": "+16195551234", "student": "Elijah", "sid": "SM123"})
        self.assertEqual(post.call_args.kwargs["data"]["To"], "+16195551234")
        self.assertEqual(post.call_args.kwargs["data"]["Body"], "Pay up")
        self.assertIn("[SENT]", self.read_log())

    def test_api_error_returns_failed_and_logs(self):
        with patch.object(twilio_api.requests, "post", return_value=self.response(400, {"message": "Invalid number"})):
            result = twilio_api.send_sms("123", "x", "Bob")
        self.assertEqual((result["status"], result["error"]), ("failed", "Invalid number"))
        self.assertIn("[FAILED]", self.read_log())

    def test_network_exception_returns_error_and_logs(self):
        with patch.object(twilio_api.requests, "post", side_effect=ConnectionError("down")):
            result = twilio_api.send_sms("6195551234", "x", "Bob")
        self.assertEqual((result["status"], result["error"]), ("error", "down"))
        self.assertIn("[ERROR]", self.read_log())

    def test_get_text_logs(self):
        self.assertEqual(twilio_api.get_text_logs(), "No text messages logged yet.")
        twilio_api.log_text_message("Al", "+1555", "hello", "sent", "SID")
        logs = twilio_api.get_text_logs()
        self.assertIn("Student: Al", logs)
        self.assertIn("hello", logs)

    def test_logging_failure_does_not_raise(self):
        with patch.object(twilio_api, "TEXT_LOG_FILE", os.path.join(self.tmp.name, "missing", "x.log")):
            twilio_api.log_text_message("Al", "+1555", "hello", "sent", "SID")


class TestEmail(unittest.TestCase):

    def test_currency_formatting(self):
        cases = {None: "$0.00", "": "$0.00", "$ -": "$0.00", "-": "$0.00", "$ 180.00": "$180.00", "$180": "$180",
                 180: "$180.00", "1,234.5": "$1,234.50", "n/a": "n/a"}
        for raw, expected in cases.items():
            self.assertEqual(email_api.format_currency_val(raw), expected, repr(raw))

    def test_total_balance_display(self):
        self.assertEqual(email_api.format_total_balance(None), "N/A")
        self.assertEqual(email_api.format_total_balance("$ 300.00"), "$300.00")

    def send(self, **overrides):
        service = MagicMock()
        service.users().messages().send().execute.return_value = {"id": "msg1"}
        kwargs = dict(creds=MagicMock(), sheet_id="S1", sheet_url="https://sheet", year_folder_id="F1",
                      start_date_str="10.05.26", end_date_str="10.11.26",
                      updated_students=[{"name": "Elijah Dinh", "hours": 2, "remaining_balance": "$0.00", "subtotal": "$120.00", "total": "$120.00"}],
                      total_balance="$120.00")
        kwargs.update(overrides)
        with patch.object(email_api, "build", return_value=service), patch.object(email_api, "NOTIFICATION_EMAIL", "me@example.com"):
            result = email_api.send_calculation_email(**kwargs)
        return result, service

    def test_sends_multipart_message_with_summary(self):
        result, service = self.send()
        self.assertEqual(result, {"status": "success", "email_id": "msg1"})
        body = service.users().messages().send.call_args.kwargs["body"]
        raw = base64.urlsafe_b64decode(body["raw"]).decode()
        self.assertIn("To: me@example.com", raw)
        self.assertIn("Subject: Tutoring Pay Calculated", raw)
        self.assertIn("multipart/alternative", raw)
        decoded = "".join(part.get_payload(decode=True).decode() for part in __import__("email").message_from_string(raw).get_payload())
        self.assertIn("Elijah Dinh", decoded)
        self.assertIn("CALCULATED", decoded)
        self.assertIn("https://drive.google.com/drive/folders/F1", decoded)
        self.assertIn("Total Balance: $120.00", decoded)

    def test_works_without_student_rows(self):
        result, _ = self.send(updated_students=None, total_balance=None)
        self.assertEqual(result["status"], "success")

    def test_failure_is_reported_not_raised(self):
        with patch.object(email_api, "build", side_effect=RuntimeError("gmail down")):
            result = email_api.send_calculation_email(MagicMock(), "S", "u", "F", "a", "b")
        self.assertEqual(result, {"status": "error", "message": "gmail down"})


class TestGoogleAuth(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.token = os.path.join(self.tmp.name, "token.pickle")
        self.patch = patch.object(google_auth, "TOKEN_PICKLE_FILE", self.token)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    class FakeCreds:
        def __init__(self, valid=True, expired=False, refresh_token=None, fail_refresh=False):
            self.valid, self.expired, self.refresh_token, self.fail_refresh = valid, expired, refresh_token, fail_refresh

        def refresh(self, request):
            if self.fail_refresh:
                raise google_auth.RefreshError("revoked")
            self.valid, self.expired = True, False

    def save(self, creds):
        with open(self.token, "wb") as f:
            pickle.dump(creds, f)

    def test_no_token_file(self):
        self.assertIsNone(google_auth.get_credentials())

    def test_valid_token_is_returned(self):
        self.save(self.FakeCreds(valid=True))
        self.assertTrue(google_auth.get_credentials().valid)

    def test_expired_token_is_refreshed_and_saved(self):
        self.save(self.FakeCreds(valid=False, expired=True, refresh_token="r"))
        creds = google_auth.get_credentials()
        self.assertTrue(creds.valid)
        with open(self.token, "rb") as f:
            self.assertTrue(pickle.load(f).valid)

    def test_failed_refresh_or_missing_refresh_token_returns_none(self):
        self.save(self.FakeCreds(valid=False, expired=True, refresh_token="r", fail_refresh=True))
        self.assertIsNone(google_auth.get_credentials())
        self.save(self.FakeCreds(valid=False, expired=True, refresh_token=None))
        self.assertIsNone(google_auth.get_credentials())

    def test_corrupt_token_file_returns_none(self):
        with open(self.token, "wb") as f:
            f.write(b"garbage")
        self.assertIsNone(google_auth.get_credentials())

    def test_redirect_uri_depends_on_host(self):
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context("/", base_url="https://dev.stepheng753.com"):
            self.assertEqual(google_auth.get_redirect_uri(), "https://dev.stepheng753.com/TutoringCalculator/login_oauth")
        with app.test_request_context("/", base_url="http://localhost:5000"):
            self.assertEqual(google_auth.get_redirect_uri(), "http://localhost:5000/TutoringCalculator/login_oauth")

    def test_initiate_flow_requests_offline_consent(self):
        flow = MagicMock()
        flow.authorization_url.return_value = ("https://accounts.google.com/auth", "state")
        with patch.object(google_auth.Flow, "from_client_secrets_file", return_value=flow) as factory:
            url = google_auth.initiate_oauth_flow("http://cb", state="swagger")
        self.assertEqual(url, "https://accounts.google.com/auth")
        self.assertEqual(factory.call_args.kwargs["redirect_uri"], "http://cb")
        self.assertEqual(flow.authorization_url.call_args.kwargs["access_type"], "offline")
        self.assertEqual(flow.authorization_url.call_args.kwargs["state"], "swagger")

    def test_callback_stores_credentials(self):
        flow = MagicMock()
        flow.credentials = self.FakeCreds(valid=True)
        with patch.object(google_auth.Flow, "from_client_secrets_file", return_value=flow):
            creds = google_auth.process_oauth_callback("http://cb", "http://cb?code=abc")
        flow.fetch_token.assert_called_once_with(authorization_response="http://cb?code=abc")
        self.assertIs(creds, flow.credentials)
        self.assertTrue(os.path.exists(self.token))

    def test_scopes_cover_every_api_used(self):
        joined = " ".join(google_auth.SCOPES)
        for api in ("calendar", "drive", "spreadsheets", "gmail.send"):
            self.assertIn(api, joined)


class TestCalendarHelpers(unittest.TestCase):

    def test_parse_date_formats(self):
        expected = datetime.date(2026, 10, 5)
        for text in ("10.05.26", "10-05-26", "10/05/26", "10.05.2026", "10-05-2026", "10/05/2026", "2026-10-05", " 10.05.26 "):
            self.assertEqual(calendar_api.parse_date_string(text), expected, text)
        with self.assertRaises(ValueError):
            calendar_api.parse_date_string("October fifth")

    def test_time_range_covers_whole_pst_days_in_utc(self):
        start, end = calendar_api.get_calendar_time_range("10.05.26", "10.11.26")
        self.assertTrue(start.startswith("2026-10-05T07:00:00"))  # PDT is UTC-7
        self.assertTrue(end.startswith("2026-10-12T06:59:59"))

    def test_calendar_id_resolution(self):
        svc = MagicMock()
        with patch.object(calendar_api.config, "GOOGLE_CALENDAR_ID", " me@group.calendar.google.com ", create=True):
            self.assertEqual(calendar_api.resolve_calendar_id(svc), "me@group.calendar.google.com")
        encoded = base64.b64encode(b"abc@group.calendar.google.com").decode().rstrip("=")
        with patch.object(calendar_api.config, "GOOGLE_CALENDAR_ID", encoded, create=True):
            self.assertEqual(calendar_api.resolve_calendar_id(svc), "abc@group.calendar.google.com")

    def test_calendar_id_falls_back_to_search_then_primary(self):
        svc = MagicMock()
        svc.calendarList().list().execute.return_value = {"items": [{"summary": "Other", "id": "o"}, {"summary": " tutoring ", "id": "t"}]}
        with patch.object(calendar_api.config, "GOOGLE_CALENDAR_ID", None, create=True):
            self.assertEqual(calendar_api.resolve_calendar_id(svc), "t")
            svc.calendarList().list().execute.return_value = {"items": []}
            self.assertEqual(calendar_api.resolve_calendar_id(svc), "primary")
            svc.calendarList().list().execute.side_effect = RuntimeError("api down")
            self.assertEqual(calendar_api.resolve_calendar_id(svc), "primary")

    def test_student_matching_rules(self):
        names = ["Elijah Dinh", "Ellie Hoang", "Michael Brower", "Michael Smith"]
        match = calendar_api.match_event_to_student
        self.assertIsNone(match("", names))
        self.assertEqual(match("Michael Brower Tutoring", names), "Michael Brower")      # full name
        self.assertEqual(match("Michael S Tutoring", names), "Michael Smith")             # first + initial
        self.assertEqual(match("Elijah Tutoring", names), "Elijah Dinh")                  # unique first name
        self.assertEqual(match("Michael Tutoring", names), "Michael Brower")              # ambiguous -> first
        self.assertEqual(match("Zed Tutoring", names), "Zed")                             # unknown -> first word
        self.assertEqual(match("elijah tutoring", []), "Elijah")                          # no roster
        self.assertIsNone(match("   ", []))


def make_event(summary, start, end, color=None):
    event = {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}}
    if color is not None:
        event["colorId"] = color
    return event


class TestCalculateTutoringHours(unittest.TestCase):

    NAMES = ["Elijah Dinh", "Ellie Hoang"]

    def run_calc(self, events, **kwargs):
        svc = MagicMock()
        svc.events().list().execute.return_value = {"items": events}
        with patch.object(calendar_api, "get_calendar_service", return_value=svc), \
             patch.object(calendar_api.config, "GOOGLE_CALENDAR_ID", "cal@example.com", create=True):
            return calendar_api.calculate_tutoring_hours(MagicMock(), "10.05.26", "10.11.26", sheet_student_names=self.NAMES, **kwargs), svc

    def test_sums_hours_under_full_and_first_name(self):
        hours, _ = self.run_calc([
            make_event("Elijah Tutoring", "2026-10-05T16:00:00-07:00", "2026-10-05T17:30:00-07:00"),
            make_event("Elijah Tutoring", "2026-10-07T16:00:00-07:00", "2026-10-07T17:00:00-07:00"),
            make_event("Ellie Tutoring", "2026-10-06T09:00:00-07:00", "2026-10-06T10:00:00-07:00"),
        ])
        self.assertEqual(hours, {"Elijah Dinh": 2.5, "Elijah": 2.5, "Ellie Hoang": 1.0, "Ellie": 1.0})

    def test_ignores_non_tutoring_colored_and_out_of_range_events(self):
        hours, _ = self.run_calc([
            make_event("Elijah Dentist", "2026-10-05T16:00:00-07:00", "2026-10-05T17:00:00-07:00"),
            make_event("Elijah Tutoring", "2026-10-05T16:00:00-07:00", "2026-10-05T17:00:00-07:00", color="4"),
            make_event("Elijah Tutoring", "2026-10-12T00:30:00-07:00", "2026-10-12T01:30:00-07:00"),   # after range
            make_event("Elijah Tutoring", "2026-10-04T23:00:00-07:00", "2026-10-05T00:30:00-07:00"),   # starts before range
            {"summary": "", "start": {}, "end": {}},
            {"summary": "Elijah Tutoring", "start": {}, "end": {}},
        ])
        self.assertEqual(hours, {})

    def test_event_is_counted_by_its_start_time(self):
        hours, _ = self.run_calc([make_event("Elijah Tutoring", "2026-10-11T23:00:00-07:00", "2026-10-12T01:00:00-07:00")])
        self.assertEqual(hours["Elijah Dinh"], 2.0)

    def test_utc_timestamps_are_converted_to_pst(self):
        # 2026-10-12T06:30Z is 2026-10-11 23:30 PDT -> inside the range
        hours, _ = self.run_calc([make_event("Elijah Tutoring", "2026-10-12T06:30:00Z", "2026-10-12T07:30:00Z")])
        self.assertEqual(hours["Elijah"], 1.0)

    def test_all_day_events_count_midnight_to_midnight(self):
        event = {"summary": "Elijah Tutoring", "start": {"date": "2026-10-06"}, "end": {"date": "2026-10-07"}}
        hours, _ = self.run_calc([event])
        self.assertEqual(hours["Elijah"], 24.0)

    def test_loads_roster_from_template_when_not_supplied(self):
        svc = MagicMock()
        svc.events().list().execute.return_value = {"items": [make_event("Ellie Tutoring", "2026-10-06T09:00:00-07:00", "2026-10-06T10:00:00-07:00")]}
        with patch.object(calendar_api, "get_calendar_service", return_value=svc), \
             patch.object(calendar_api.config, "GOOGLE_CALENDAR_ID", "cal@example.com", create=True), \
             patch(f"{DRIVE}.get_student_names_from_sheet", return_value=self.NAMES) as roster:
            hours = calendar_api.calculate_tutoring_hours(MagicMock(), "10.05.26", "10.11.26")
        roster.assert_called_once()
        self.assertIn("Ellie Hoang", hours)

    def test_unknown_calendar_falls_back_to_tutoring_calendar(self):
        svc = MagicMock()
        not_found = HttpError(MagicMock(status=404), b"not found")
        good = {"items": [make_event("Elijah Tutoring", "2026-10-05T16:00:00-07:00", "2026-10-05T17:00:00-07:00")]}
        svc.events().list().execute.side_effect = [not_found, good]
        svc.calendarList().list().execute.return_value = {"items": [{"summary": "Weekly Tutoring Hours", "id": "found-cal"}]}
        with patch.object(calendar_api, "get_calendar_service", return_value=svc), \
             patch.object(calendar_api.config, "GOOGLE_CALENDAR_ID", "stale@example.com", create=True):
            hours = calendar_api.calculate_tutoring_hours(MagicMock(), "10.05.26", "10.11.26", sheet_student_names=self.NAMES)
        self.assertEqual(hours["Elijah"], 1.0)

    def test_404_without_any_tutoring_calendar_raises(self):
        svc = MagicMock()
        svc.events().list().execute.side_effect = HttpError(MagicMock(status=404), b"nf")
        svc.calendarList().list().execute.return_value = {"items": [{"summary": "Birthdays", "id": "b"}]}
        with patch.object(calendar_api, "get_calendar_service", return_value=svc), \
             patch.object(calendar_api.config, "GOOGLE_CALENDAR_ID", "stale@example.com", create=True):
            with self.assertRaises(HttpError):
                calendar_api.calculate_tutoring_hours(MagicMock(), "10.05.26", "10.11.26", sheet_student_names=self.NAMES)

    def test_other_http_errors_propagate(self):
        svc = MagicMock()
        svc.events().list().execute.side_effect = HttpError(MagicMock(status=500), b"boom")
        with patch.object(calendar_api, "get_calendar_service", return_value=svc), \
             patch.object(calendar_api.config, "GOOGLE_CALENDAR_ID", "cal@example.com", create=True):
            with self.assertRaises(HttpError):
                calendar_api.calculate_tutoring_hours(MagicMock(), "10.05.26", "10.11.26", sheet_student_names=self.NAMES)


class TestSheetHelpers(unittest.TestCase):

    def test_parse_currency(self):
        cases = {None: 0.0, 5: 5.0, "$ 180.00": 180.0, "$1,234.50": 1234.5, "": 0.0, "n/a": 0.0, "-$20": -20.0, "1.2.3": 0.0}
        for raw, expected in cases.items():
            self.assertEqual(drive_sheets_api.parse_currency(raw), expected, repr(raw))

    def test_student_name_validation(self):
        valid = drive_sheets_api.is_valid_student_name
        self.assertTrue(valid("Elijah Dinh"))
        for bad in (None, "", "  ", "Al Li", "123456", "Total", "SUBTOTALS"):
            self.assertFalse(valid(bad), repr(bad))

    def test_previous_week_dates(self):
        self.assertEqual(drive_sheets_api.get_previous_week_dates("01.05.26"), ("12.29.25", "01.04.26", "2025"))

    def test_year_folder_found_or_created(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": [{"id": "existing"}]}
        with patch.object(drive_sheets_api.config, "PAY_PARENT_FOLDER_ID", "parent", create=True):
            self.assertEqual(drive_sheets_api.get_or_create_year_folder(drive, "2026"), "existing")
            drive.files().list().execute.return_value = {"files": []}
            drive.files().create().execute.return_value = {"id": "new"}
            self.assertEqual(drive_sheets_api.get_or_create_year_folder(drive, "2027"), "new")
        self.assertEqual(drive.files().create.call_args.kwargs["body"]["parents"], ["parent"])

    def test_find_file_in_folder(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": []}
        self.assertIsNone(drive_sheets_api.find_file_in_folder(drive, "x", "f"))
        drive.files().list().execute.return_value = {"files": [{"id": "1"}, {"id": "2"}]}
        self.assertEqual(drive_sheets_api.find_file_in_folder(drive, "x", "f"), {"id": "1"})

    def sheets(self, values):
        svc = MagicMock()
        svc.spreadsheets().values().get().execute.return_value = {"values": values}
        return svc

    def test_student_names_stop_at_first_invalid_row(self):
        svc = self.sheets([["Elijah Dinh"], ["Ellie Hoang"], ["6"], ["Michael Brower"]])
        with patch(f"{DRIVE}.get_sheets_service", return_value=svc):
            self.assertEqual(drive_sheets_api.get_student_names_from_sheet(MagicMock(), "sheet"), ["Elijah Dinh", "Ellie Hoang"])

    def test_student_names_edge_cases(self):
        with patch.object(drive_sheets_api.config, "TEMPLATE_SHEET_ID", None, create=True), patch(f"{DRIVE}.get_sheets_service"):
            self.assertEqual(drive_sheets_api.get_student_names_from_sheet(MagicMock()), [])
        svc = MagicMock()
        svc.spreadsheets().values().get().execute.side_effect = RuntimeError("api")
        with patch(f"{DRIVE}.get_sheets_service", return_value=svc):
            self.assertEqual(drive_sheets_api.get_student_names_from_sheet(MagicMock(), "sheet"), [])

    def test_copy_template_creates_sheet_and_sets_dates(self):
        drive, sheets = MagicMock(), MagicMock()
        drive.files().list().execute.return_value = {"files": []}          # no approved or CALCULATED sheet yet
        drive.files().copy().execute.return_value = {"id": "new_sheet", "name": "n"}
        with patch(f"{DRIVE}.get_drive_service", return_value=drive), patch(f"{DRIVE}.get_sheets_service", return_value=sheets), \
             patch(f"{DRIVE}.get_or_create_year_folder", return_value="year"), \
             patch(f"{DRIVE}.find_file_in_folder", return_value=None), \
             patch.object(drive_sheets_api.config, "TEMPLATE_SHEET_ID", "tmpl", create=True):
            result = drive_sheets_api.copy_template_sheet(MagicMock(), "10.05.26", "10.11.26")
        self.assertEqual(result["title"], "10.05.26 - 10.11.26 CALCULATED")
        self.assertEqual(result["sheet_id"], "new_sheet")
        self.assertEqual(drive.files().copy.call_args.kwargs["fileId"], "tmpl")
        update = sheets.spreadsheets().values().update.call_args.kwargs
        self.assertEqual((update["range"], update["body"]), ("C1:D1", {"values": [["10.05.26", "10.11.26"]]}))

    def test_copy_template_replaces_stale_calculated_sheet(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": [{"id": "old", "name": "10.05.26 - 10.11.26 CALCULATED"}]}
        drive.files().copy().execute.return_value = {"id": "fresh"}
        with patch(f"{DRIVE}.get_drive_service", return_value=drive), patch(f"{DRIVE}.get_sheets_service", return_value=MagicMock()), \
             patch(f"{DRIVE}.get_or_create_year_folder", return_value="year"), \
             patch(f"{DRIVE}.find_file_in_folder", return_value={"id": "old"}), \
             patch.object(drive_sheets_api.config, "TEMPLATE_SHEET_ID", "tmpl", create=True):
            result = drive_sheets_api.copy_template_sheet(MagicMock(), "10.05.26", "10.11.26")
        drive.files().delete.assert_called_with(fileId="old")
        self.assertEqual(result["sheet_id"], "fresh")

    def test_previous_balances_with_no_previous_sheet(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": []}
        with patch(f"{DRIVE}.get_drive_service", return_value=drive), patch(f"{DRIVE}.get_sheets_service"), \
             patch(f"{DRIVE}.get_or_create_year_folder", return_value="year"):
            self.assertEqual(drive_sheets_api.get_previous_balances(MagicMock(), "10.12.26", "10.18.26"), {})

    def test_hours_and_balances_updates_columns_and_reads_totals(self):
        svc = MagicMock()
        get = svc.spreadsheets().values().get
        get().execute.side_effect = [
            {"values": [["", "Elijah Dinh"], ["Need to Pay", "Ellie Hoang"], ["", "6"]]},                     # B5:C
            {"values": [["Elijah Dinh", "2", "$60", "$120", "$10", "$130"], ["Ellie Hoang", "0", "$60", "$0", "$0", "$0"]]},  # C5:H6
            {"values": [["$130.00"]]},                                                                          # H7 summary
        ]
        with patch(f"{DRIVE}.get_sheets_service", return_value=svc):
            result = drive_sheets_api.update_sheet_hours_and_balances(
                MagicMock(), "sheet", {"Elijah": 2.0}, {"Elijah Dinh": 10.0})
        batch = svc.spreadsheets().values().batchUpdate.call_args.kwargs["body"]["data"]
        by_range = {d["range"]: d["values"] for d in batch}
        self.assertEqual(by_range["D5:D6"], [[2.0], [0.0]])
        self.assertEqual(by_range["G5:G6"], [[10.0], [0.0]])
        self.assertEqual(by_range["B6"], [[""]])  # Ellie has 0 hours: stale status cleared
        self.assertEqual(result["total_balance"], "$130.00")
        self.assertEqual([s["name"] for s in result["updated_students"]], ["Elijah Dinh", "Ellie Hoang"])
        self.assertEqual(result["updated_students"][0]["total"], "$130")

    def test_hours_and_balances_with_no_students_skips_write(self):
        svc = MagicMock()
        svc.spreadsheets().values().get().execute.return_value = {"values": []}
        with patch(f"{DRIVE}.get_sheets_service", return_value=svc):
            result = drive_sheets_api.update_sheet_hours_and_balances(MagicMock(), "sheet", {}, {})
        svc.spreadsheets().values().batchUpdate.assert_not_called()
        self.assertEqual(result["updated_students"], [])

    def test_hours_and_balances_falls_back_when_formatted_read_fails(self):
        svc = MagicMock()
        svc.spreadsheets().values().get().execute.side_effect = [
            {"values": [["", "Elijah Dinh"]]}, RuntimeError("read failed"), RuntimeError("no summary"), RuntimeError("no column H")]
        with patch(f"{DRIVE}.get_sheets_service", return_value=svc):
            result = drive_sheets_api.update_sheet_hours_and_balances(MagicMock(), "sheet", {"Elijah Dinh": 2.0}, {})
        self.assertEqual(result["updated_students"][0]["total"], "$120.00")
        self.assertEqual(result["total_balance"], "")

    def test_pending_recipients_blocked_while_title_has_calculated(self):
        drive = MagicMock()
        drive.files().get().execute.return_value = {"name": "10.05.26 - 10.11.26 calculated"}
        with patch(f"{DRIVE}.get_drive_service", return_value=drive):
            result = drive_sheets_api.get_pending_text_recipients(MagicMock(), "sheet")
        self.assertTrue(result["is_pending_review"])
        self.assertEqual(result["recipients"], [])

    def test_pending_recipients_rules(self):
        drive = MagicMock()
        drive.files().get().execute.return_value = {"name": "10.05.26 - 10.11.26"}
        row = lambda status, name, bal, phone="6195551234", text="Hi": [status, name, "2", "$60", "$120", "$0", bal, "", "", phone, text]
        svc = MagicMock()
        svc.spreadsheets().values().get().execute.return_value = {"values": [
            row("", "Elijah Dinh", "$120.00"),                 # eligible
            row("Need to Pay", "Ellie Hoang", "$60.00"),       # already notified
            row("", "Michael Brower", "$0.00"),                # nothing owed
            row("", "Amelie Meeker", "$60.00", phone=""),      # no phone
            row("", "Jack Glandorf", "$60.00", text=""),       # no message
            row("", "Zed Zhang", "$45.00"),                    # eligible
            ["", "Total"],                                     # summary row stops the scan
            row("", "Never Reached", "$99.00"),
        ]}
        with patch(f"{DRIVE}.get_drive_service", return_value=drive), patch(f"{DRIVE}.get_sheets_service", return_value=svc):
            result = drive_sheets_api.get_pending_text_recipients(MagicMock(), "sheet")
        self.assertFalse(result["is_pending_review"])
        self.assertEqual([r["student"] for r in result["recipients"]], ["Elijah Dinh", "Zed Zhang"])
        self.assertEqual(result["recipients"][0]["row_num"], 5)
        self.assertEqual(result["recipients"][0]["total_balance"], 120.0)

    def test_find_current_week_sheets(self):
        drive = MagicMock()
        drive.files().list().execute.return_value = {"files": [{"id": "a"}, {"id": "b"}]}
        with patch(f"{DRIVE}.get_drive_service", return_value=drive), patch(f"{DRIVE}.get_or_create_year_folder", return_value="year"):
            self.assertEqual(len(drive_sheets_api.find_current_week_sheets(MagicMock(), "10.05.26", "10.11.26")), 2)
            self.assertEqual(drive_sheets_api.find_current_week_sheet(MagicMock(), "10.05.26", "10.11.26"), {"id": "a"})
            drive.files().list().execute.return_value = {"files": []}
            self.assertIsNone(drive_sheets_api.find_current_week_sheet(MagicMock(), "10.05.26", "10.11.26"))


if __name__ == "__main__":
    unittest.main()
