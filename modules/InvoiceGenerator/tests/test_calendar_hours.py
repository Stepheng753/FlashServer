"""Calc Hours tests: event filtering and range math, with the Google Calendar API mocked."""
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch, MagicMock

from flask import Flask

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.InvoiceGenerator import calendar_hours as ch
from modules.InvoiceGenerator.routes import invoice_bp


def event(start, end, summary="Busy", **extra):
    return {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}, **extra}


# 2026-10 is PDT (UTC-7), so 17:00Z-19:00Z is 10:00-12:00 local
OCT_START, OCT_END = date(2026, 10, 1), date(2026, 11, 1)


class ComputeHoursTests(unittest.TestCase):

    def test_sums_busy_events(self):
        events = [
            event("2026-10-05T10:00:00-07:00", "2026-10-05T12:00:00-07:00"),
            event("2026-10-06T10:00:00-07:00", "2026-10-06T10:30:00-07:00"),
        ]
        self.assertEqual(ch.compute_hours(events, OCT_START, OCT_END), (2.5, 2))

    def test_overlaps_double_count(self):
        events = [
            event("2026-10-05T10:00:00-07:00", "2026-10-05T12:00:00-07:00"),
            event("2026-10-05T11:00:00-07:00", "2026-10-05T13:00:00-07:00"),
        ]
        self.assertEqual(ch.compute_hours(events, OCT_START, OCT_END), (4.0, 2))

    def test_excludes_tentative_cancelled_free_and_all_day(self):
        slot = ("2026-10-05T10:00:00-07:00", "2026-10-05T11:00:00-07:00")
        events = [
            event(*slot),
            event(*slot, status="tentative"),
            event(*slot, status="cancelled"),
            event(*slot, transparency="transparent"),
            event(*slot, summary="Tentative"),
            {"summary": "Busy", "start": {"date": "2026-10-07"}, "end": {"date": "2026-10-08"}},
        ]
        self.assertEqual(ch.compute_hours(events, OCT_START, OCT_END), (1.0, 1))

    def test_event_clipped_at_window_boundary(self):
        # Local 2026-10-31 23:00 to 2026-11-01 01:00 -> only 1 hour is in October
        events = [event("2026-10-31T23:00:00-07:00", "2026-11-01T01:00:00-07:00")]
        self.assertEqual(ch.compute_hours(events, OCT_START, OCT_END), (1.0, 1))

    def test_minutes_sum_without_rounding_drift(self):
        events = [event(f"2026-10-0{d}T10:00:00-07:00", f"2026-10-0{d}T10:20:00-07:00") for d in (5, 6, 7)]
        self.assertEqual(ch.compute_hours(events, OCT_START, OCT_END), (1.0, 3))

    def test_busy_events_detail_is_local_and_clipped(self):
        events = [event("2026-10-31T23:00:00-07:00", "2026-11-01T01:00:00-07:00", summary="Late call")]
        self.assertEqual(
            ch.busy_events(events, OCT_START, OCT_END),
            [{"date": "2026-10-31", "start": "23:00", "end": "00:00", "title": "Late call", "minutes": 60}],
        )

    def test_utc_timestamps(self):
        events = [event("2026-10-05T17:00:00Z", "2026-10-05T19:00:00Z")]
        self.assertEqual(ch.compute_hours(events, OCT_START, OCT_END), (2.0, 1))


class LoadSourcesTests(unittest.TestCase):

    def test_skips_incomplete_entries(self):
        cfg = {"HOURS_CALENDARS": [{"name": "TIP", "calendar_id": "stephen@torreypinesconsulting.com"}, {"name": "x"}]}
        with patch.object(ch, "get_config", return_value=cfg):
            self.assertEqual(ch.load_calendar_sources(), [{"name": "TIP", "calendar_id": "stephen@torreypinesconsulting.com"}])


class ColorTests(unittest.TestCase):

    def test_valid_hex_passes_through_and_junk_is_dropped(self):
        self.assertEqual(ch._valid_color("#55b080"), "#55b080")
        for bad in ("red", "#abc", "url(x)", "#55b08g", None, 5):
            self.assertIsNone(ch._valid_color(bad))

    def test_calculate_hours_returns_configured_color(self):
        sources = [{"name": "A", "calendar_id": "a@x.com", "color": "#bc2b2e"}, {"name": "B", "calendar_id": "b@x.com"}]
        with patch.object(ch, "fetch_events", return_value=[]):
            rows = ch.calculate_hours("month", sources=sources, service=MagicMock())["calendars"]
        self.assertEqual([r["color"] for r in rows], ["#bc2b2e", None])


class FetchEventsTests(unittest.TestCase):

    def test_follows_pagination_and_expands_recurrences(self):
        service = MagicMock()
        listing = service.events.return_value.list
        listing.return_value.execute.side_effect = [
            {"items": [{"id": "a"}], "nextPageToken": "p2"},
            {"items": [{"id": "b"}]},
        ]
        events = ch.fetch_events(service, "cal@x.com", OCT_START, OCT_END)
        self.assertEqual([e["id"] for e in events], ["a", "b"])
        first, second = listing.call_args_list
        self.assertTrue(first.kwargs["singleEvents"])
        self.assertEqual(first.kwargs["calendarId"], "cal@x.com")
        self.assertEqual(first.kwargs["timeMin"], "2026-10-01T07:00:00+00:00")
        self.assertEqual(second.kwargs["pageToken"], "p2")


class ResolveRangeTests(unittest.TestCase):
    today = date(2026, 10, 23)  # a Friday

    def test_week_starts_monday(self):
        self.assertEqual(ch.resolve_range("week", self.today), (date(2026, 10, 19), date(2026, 10, 26)))

    def test_month(self):
        self.assertEqual(ch.resolve_range("month", self.today), (date(2026, 10, 1), date(2026, 11, 1)))

    def test_last_month_across_year(self):
        self.assertEqual(ch.resolve_range("last_month", date(2026, 1, 15)), (date(2025, 12, 1), date(2026, 1, 1)))

    def test_year(self):
        self.assertEqual(ch.resolve_range("year", self.today), (date(2026, 1, 1), date(2027, 1, 1)))

    def test_custom_end_is_inclusive(self):
        self.assertEqual(
            ch.resolve_range("custom", self.today, "2026-10-01", "2026-10-03"),
            (date(2026, 10, 1), date(2026, 10, 4)),
        )

    def test_custom_requires_dates_and_order(self):
        with self.assertRaises(ValueError):
            ch.resolve_range("custom", self.today)
        with self.assertRaises(ValueError):
            ch.resolve_range("custom", self.today, "2026-10-05", "2026-10-01")


class HoursApiTests(unittest.TestCase):

    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(invoice_bp)
        self.client = app.test_client()

    def test_partial_failure_still_totals(self):
        sources = [{"name": "Good", "calendar_id": "good@x.com"}, {"name": "Bad", "calendar_id": "bad@x.com"}]

        def fake_fetch(service, calendar_id, start, end):
            if calendar_id == "bad@x.com":
                raise RuntimeError("404")
            return [event("2026-10-05T10:00:00-07:00", "2026-10-05T12:00:00-07:00")]

        with patch.object(ch, "load_calendar_sources", return_value=sources), \
                patch.object(ch, "get_service", return_value=MagicMock()), \
                patch.object(ch, "fetch_events", side_effect=fake_fetch):
            res = self.client.get("/api/invoices/hours?range=year")
        body = res.get_json()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(body["calendars"][0]["hours"], 2.0)
        self.assertEqual(body["calendars"][0]["events"][0]["minutes"], 120)
        self.assertEqual(body["calendars"][1]["events"], [])
        self.assertEqual(body["calendars"][1]["error"], "Could not read calendar (RuntimeError)")
        self.assertEqual(body["total_hours"], 2.0)

    def test_unauthorized_returns_401(self):
        with patch.object(ch, "load_calendar_sources", return_value=[{"name": "A", "calendar_id": "a@x.com"}]), \
                patch.object(ch, "get_credentials", return_value=None):
            self.assertEqual(self.client.get("/api/invoices/hours").status_code, 401)
            self.assertEqual(self.client.get("/api/invoices/hours/calendars").status_code, 401)

    def test_list_calendars(self):
        service = MagicMock()
        service.calendarList.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "a@x.com", "summary": "PWL", "accessRole": "freeBusyReader"}]
        }
        with patch.object(ch, "get_service", return_value=service):
            res = self.client.get("/api/invoices/hours/calendars")
        self.assertEqual(res.get_json(), [{"id": "a@x.com", "name": "PWL", "access": "freeBusyReader"}])

    def test_bad_range_returns_400(self):
        self.assertEqual(self.client.get("/api/invoices/hours?range=bogus").status_code, 400)
        self.assertEqual(self.client.get("/api/invoices/hours?range=custom").status_code, 400)


if __name__ == "__main__":
    unittest.main()
