import json
import re
from datetime import date, datetime, timedelta

import pytz
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from modules.TutoringCalculator.apis.google_auth import get_credentials
from modules.TutoringCalculator.config import get_config
from .config import APP_TIMEZONE

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
RANGE_KEYS = ("week", "month", "last_month", "year", "custom")


class CalendarAuthError(Exception):
    pass


def load_calendar_sources():
    """Returns [{name, calendar_id, color?}] from HOURS_CALENDARS in config/config.json."""
    sources = get_config().get("HOURS_CALENDARS", [])
    return [s for s in sources if s.get("name") and s.get("calendar_id")]


def _valid_color(color):
    return color if isinstance(color, str) and HEX_COLOR.match(color) else None


def get_service():
    creds = get_credentials()
    if not creds:
        raise CalendarAuthError("Google is not authorized. Visit /login_oauth to sign in.")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def list_calendars(service=None):
    """Lists every calendar visible to the main account so IDs can be copied into config."""
    service = service or get_service()
    items = service.calendarList().list().execute().get("items", [])
    return [
        {"id": c["id"], "name": c.get("summaryOverride") or c.get("summary", ""), "access": c.get("accessRole", "")}
        for c in items
    ]


def resolve_range(key, today=None, custom_start=None, custom_end=None):
    """Maps a range key to (start, end) dates; end is exclusive."""
    today = today or datetime.now(APP_TIMEZONE).date()
    if key == "week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=7)
    if key == "month":
        start = today.replace(day=1)
        return start, _first_of_next_month(start)
    if key == "last_month":
        end = today.replace(day=1)
        return (end - timedelta(days=1)).replace(day=1), end
    if key == "year":
        return date(today.year, 1, 1), date(today.year + 1, 1, 1)
    if key == "custom":
        if not custom_start or not custom_end:
            raise ValueError("Custom range needs start and end dates")
        start = date.fromisoformat(custom_start)
        end = date.fromisoformat(custom_end) + timedelta(days=1)
        if end <= start:
            raise ValueError("End date must be on or after start date")
        return start, end
    raise ValueError(f"Unknown range '{key}'")


def _first_of_next_month(d):
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _is_counted(event):
    """Busy events only: timed, not cancelled, not tentative, not marked free."""
    if event.get("status") in ("cancelled", "tentative"):
        return False
    if event.get("transparency") == "transparent":
        return False
    # Busy-only shares replace the real title with "Busy" or "Tentative"
    if (event.get("summary") or "").strip().lower() == "tentative":
        return False
    return True


def _parse_dt(value):
    """Returns an aware datetime for timed events, or None for all-day events."""
    raw = value.get("dateTime")
    if not raw:
        return None
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt if dt.tzinfo else APP_TIMEZONE.localize(dt)


def _hours(counted):
    return round(sum(e["minutes"] for e in counted) / 60, 2)


def busy_events(events, start, end):
    """Returns counted events clipped to [start, end) as {date, start, end, title, minutes} dicts."""
    window_start = APP_TIMEZONE.localize(datetime.combine(start, datetime.min.time()))
    window_end = APP_TIMEZONE.localize(datetime.combine(end, datetime.min.time()))
    counted = []
    for event in events:
        ev_start = _parse_dt(event.get("start", {}))
        ev_end = _parse_dt(event.get("end", {}))
        if not ev_start or not ev_end or not _is_counted(event):
            continue
        clipped_start = max(ev_start, window_start).astimezone(APP_TIMEZONE)
        clipped_end = min(ev_end, window_end).astimezone(APP_TIMEZONE)
        if clipped_end <= clipped_start:
            continue
        counted.append({
            "date": clipped_start.date().isoformat(),
            "start": clipped_start.strftime("%H:%M"),
            "end": clipped_end.strftime("%H:%M"),
            "title": event.get("summary") or "(no title)",
            "minutes": int(round((clipped_end - clipped_start).total_seconds() / 60)),
        })
    return counted


def compute_hours(events, start, end):
    """Sums busy-event durations inside [start, end); returns (hours, event_count)."""
    counted = busy_events(events, start, end)
    return _hours(counted), len(counted)


def fetch_events(service, calendar_id, start, end):
    """Pulls every event in [start, end) with recurring events expanded."""
    time_min = APP_TIMEZONE.localize(datetime.combine(start, datetime.min.time())).astimezone(pytz.UTC)
    time_max = APP_TIMEZONE.localize(datetime.combine(end, datetime.min.time())).astimezone(pytz.UTC)
    events = []
    page_token = None
    while True:
        resp = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
            pageToken=page_token,
        ).execute()
        events.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            return events


def _http_reason(error):
    try:
        return json.loads(error.content.decode("utf-8"))["error"]["message"]
    except Exception:
        return error.reason or "unknown error"


def calculate_hours(range_key, custom_start=None, custom_end=None, sources=None, today=None, service=None):
    start, end = resolve_range(range_key, today, custom_start, custom_end)
    sources = load_calendar_sources() if sources is None else sources
    calendars = []
    if sources:
        service = service or get_service()
    for source in sources:
        row = {"name": source["name"], "color": _valid_color(source.get("color")), "hours": 0, "event_count": 0, "events": []}
        try:
            events = fetch_events(service, source["calendar_id"], start, end)
            counted = busy_events(events, start, end)
            row["events"] = counted
            row["event_count"] = len(counted)
            row["hours"] = _hours(counted)
        except HttpError as e:
            row["error"] = f"Google API error {e.resp.status}: {_http_reason(e)}"
        except Exception as e:
            row["error"] = f"Could not read calendar ({type(e).__name__})"
        calendars.append(row)
    return {
        "range": {"start": start.isoformat(), "end": (end - timedelta(days=1)).isoformat()},
        "calendars": calendars,
        "total_hours": round(sum(c["hours"] for c in calendars), 2),
    }
