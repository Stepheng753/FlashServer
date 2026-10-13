# TutoringCalculator Testing

Tests: [modules/TutoringCalculator/tests/](../../modules/TutoringCalculator/tests/)

```bash
.venv/bin/python -m unittest discover -s modules/TutoringCalculator/tests -p "test_*.py"
```

All Google (Calendar, Drive, Sheets, Gmail, OAuth) and Twilio calls are mocked with `unittest.mock.patch`. The tests need no credentials, send nothing, and write to temporary files only (never `logs/text_messages.log` or `keys/token.pickle`).

## `test_tutoring_calc.py`

Hours parsing, previous-balance status matching, pay-status handling when hours are zero, a calendar event spanning Sunday to Monday, duplicate-sheet blocking, the orchestration with `send_email` true and false, and the already-approved safeguard (see [approval-safeguard.md](approval-safeguard.md)).

## `test_tutoring_apis.py`

| Class | What it checks |
| :--- | :--- |
| `TestConfig` | Values come from `config.json` and `secrets.json`, re-read on each access, missing or broken files, fallback to the base directory, OAuth file resolution, unknown attribute. |
| `TestTwilio` | E.164 formatting, send success / API error / network error (each logged), reading the log, a logging failure never raises. |
| `TestEmail` | Currency formatting, the multipart message (recipient, subject, student rows, folder link), no student rows, Gmail failure returned not raised. |
| `TestGoogleAuth` | Valid, expired-and-refreshed, failed refresh, no refresh token, and corrupt token files. Redirect URI per host. OAuth start and callback. Required scopes. |
| `TestCalendarHelpers` | Every supported date format, PST-to-UTC range, calendar ID resolution (configured, base64, search by name, `primary`), student name matching rules. |
| `TestCalculateTutoringHours` | Hours summed under full and first name. Ignored: events not ending in "Tutoring", colored events, events outside the range. Counted by start time, UTC conversion, all-day events, roster loaded from the template, 404 fallback to a Tutoring calendar, other API errors propagate. |
| `TestSheetHelpers` | Currency and student-name parsing, year folder find or create, copying the template (and replacing a stale CALCULATED sheet), previous balances, hours and balances written to the sheet, fallbacks when reads fail, who gets a text (`get_pending_text_recipients`), finding the week's sheets. |

## `test_tutoring_routes.py`

Uses a Flask app with only `tutoring_bp` and a patched `get_credentials`.

| Class | What it checks |
| :--- | :--- |
| `TestBillingDates` | The week starts on the most recent Monday, and on a Monday it is the week that just ended. This includes Sunday and a week spanning New Year. |
| `TestPagesAndOAuth`, `TestYearFolderLookup` | Public privacy page, dashboard, login redirect and callback success / failure, folder URL caching. |
| `TestStatus` | Logged-out state with auth URL, opt-in sheet lookup, pending-review vs approved sheets, duplicate sheets, lookup errors. |
| `TestRunCalc` | 401 when logged out, default and explicit dates, `send_email` parsing, email failure, already-approved short-circuit, 500 on failure, legacy URLs. |
| `TestSendTexts` | 401, no sheet (404), duplicate sheets (400), `CALCULATED` title blocks sending, nobody to text, texts sent and pay status updated, singular wording, 500. |
| `TestStepwiseEndpoints`, `TestUpdateSheet` | Dates, text log, copy template, calc hours, previous balances, and every `update-sheet` action and error. |
