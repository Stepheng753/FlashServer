# TutoringCalculator Module

The `TutoringCalculator` package provides automated billing calculations, Google Calendar event parsing, Google Drive/Sheets operations, parent text messaging via Twilio, and calculation email notifications for Crossroads Tutoring.

---

## 1. Endpoints Reference

All Tutoring Calculator endpoints use the canonical `/api/tutoring/` prefix (with backwards-compatible aliases at `/tutoring/`, `/api/`, and root paths):

### `GET /api/tutoring/status`
* **Purpose**: Fetches dashboard status, current week billing dates, Google OAuth authorization status, and optionally verifies the existence/title of the current week's Google Sheet in Drive.
* **Query Parameters**: `check_sheet` (`1` or `true` to check Drive).
* **Response**:
  ```json
  {
    "is_authenticated": true,
    "auth_url": null,
    "dates": {
      "start_date": "08.31.26",
      "end_date": "09.06.26",
      "start_date_full": "2026-08-31",
      "end_date_full": "2026-09-06"
    },
    "pay_parent_folder_id": "12hcaaHrab8TCFO8hi_cC67FRBHIU-Xsx",
    "pay_parent_folder_url": "https://drive.google.com/drive/folders/12hcaaHrab8TCFO8hi_cC67FRBHIU-Xsx",
    "current_year": "2026",
    "year_folder_url": "https://drive.google.com/drive/folders/12hcaaHrab8TCFO8hi_cC67FRBHIU-Xsx",
    "current_sheet": {
      "id": "1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA",
      "name": "08.31.26 - 09.06.26",
      "sheet_url": "https://docs.google.com/spreadsheets/d/1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA/edit",
      "is_pending_review": false,
      "status_label": "Approved"
    },
    "current_sheets": [...],
    "has_multiple_sheets": false
  }
  ```

### `POST /api/tutoring/run-calc`
* **Purpose**: One-click orchestration endpoint for weekly pay calculations.
* **Query/JSON Parameters**: `start_date`, `end_date`, `send_email` (`true`/`false`, default: `true`).
* **Behavior**: Clones the template, extracts Google Calendar hours, checks previous unpaid balances, populates Google Sheet, and optionally emails calculation summary.

### `POST /api/tutoring/run-send-texts` (or `/api/tutoring/send-texts`)
* **Purpose**: One-click SMS dispatch to parents with unpaid balances.
* **Parameters**: `sheet_id` (optional; auto-detected if omitted).
* **Behavior**: Checks if `CALCULATED` is present in the title (aborts if not yet approved by human), sends Twilio SMS to eligible parents, marks student status as `Need to Pay`, and logs to `logs/text_messages.log`.

### `GET /api/tutoring/dates`
* **Purpose**: Calculates the billing week range.
* **Logic**: Calculates the previous Monday (if called on Monday, calculates 7 days back) and the following Sunday.
* **Response**:
  ```json
  {
    "start_date": "08.31.26",
    "end_date": "09.06.26",
    "start_date_full": "2026-08-31",
    "end_date_full": "2026-09-06"
  }
  ```

### `POST /api/tutoring/copy-template`
* **Parameters** (JSON or query): `start_date`, `end_date` (optional; computed automatically if omitted).
* **Behavior**:
  1. Finds or creates the folder named after the start date's year (e.g., `2026`) inside `Pay Parent Folder`.
  2. Copies the master template (`Student Pay`).
  3. Renames the copy to `MM.DD.YY - MM.DD.YY CALCULATED`.
  4. Sets cell `C1` to `start_date` and `D1` to `end_date`.
* **Response**:
  ```json
  {
    "status": "success",
    "sheet_id": "1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA",
    "sheet_url": "https://docs.google.com/spreadsheets/d/1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA/edit",
    "title": "08.31.26 - 09.06.26 CALCULATED",
    "year_folder_id": "12hcaaHrab8TCFO8hi_cC67FRBHIU-Xsx"
  }
  ```

### `GET /api/tutoring/calc-hours`
* **Parameters**: `start_date`, `end_date`.
* **Behavior**:
  1. Fetches events from the "Tutoring" calendar between `start_date 00:00:00` and `end_date 23:59:59` PST.
  2. Filters for events where the last word of the title is `"Tutoring"` and `colorId` is default/primary (`None`).
  3. Consolidates hours by the first word of the event title (student first name).
* **Response**:
  ```json
  {
    "Elijah": 3.0,
    "Ellie": 4.5,
    "Amelie": 4.0,
    "Michael": 5.75,
    "Jack": 3.0
  }
  ```

### `GET /api/tutoring/previous-balances`
* **Parameters**: `start_date`, `end_date`.
* **Behavior**:
  1. Locates the sheet from the previous week (7 days prior to `start_date`).
  2. Scans for rows where `Student Status == "Need to Pay"`.
  3. Returns a dictionary mapping student first names to their unpaid balances.
* **Response**:
  ```json
  {
    "Elijah": 180.0,
    "Ellie": 270.0
  }
  ```

### `POST /api/tutoring/update-sheet`
* **Parameters** (JSON or query):
  * `sheet_id` (string, required)
  * `action` (`update_hours` or `update_pay_status`, required)
* **Actions**:
  * `update_hours`:
    * Calls `calc-hours` and matches student first names from row 5 down, writing hours to Column D.
    * Calls `previous-balances` and writes remaining balances to Column G.
    * Sends an email notification to `stepheng753@gmail.com` with links to the sheet and folder.
    * Returns `sheet_url` and update breakdown.
  * `update_pay_status`:
    * Converts blank student statuses in Column B to `"Need to Pay"`.

### `GET /api/tutoring/text-logs`
* **Behavior**: Returns the raw text of `logs/text_messages.log`.

---

## 2. Approval Workflow (`CALCULATED` Title)

To ensure messages are never sent accidentally before you review the numbers:
1. When `run_calc.py` (or `copy-template`) creates a new weekly sheet, it is named:
   `MM.DD.YY - MM.DD.YY CALCULATED`
2. You receive an email linking directly to the sheet and pay folder.
3. Open the sheet and review the hours and balances.
4. **To approve**: Simply rename the sheet in Google Drive / Google Sheets to remove `CALCULATED` (e.g., `08.31.26 - 09.06.26`).
5. When `run_send_texts.py` runs (or `/send-texts` is called), it checks the title:
   * If `CALCULATED` is present $\rightarrow$ Aborts without sending.
   * If `CALCULATED` is removed $\rightarrow$ Sends texts and marks students as `Need to Pay`.

---

## 3. Running Automation Scripts Manually

### Running Pay Calculation:
```bash
python3 TutoringCalculator/scripts/run_calc.py
```

### Running SMS Dispatch:
```bash
python3 TutoringCalculator/scripts/run_send_texts.py
# Or supply a specific sheet ID:
python3 TutoringCalculator/scripts/run_send_texts.py <SHEET_ID>
```

---

## 4. Package Structure

```
TutoringCalculator/
├── __init__.py                # Blueprint export (tutoring_bp)
├── config.py                  # Twilio, Google, and PST timezone configurations
├── routes.py                  # Web & REST API endpoints
├── apis/                      # Service client integrations
│   ├── __init__.py
│   ├── calendar_api.py        # Google Calendar scraper for tutoring events
│   ├── drive_sheets_api.py    # Google Sheets template cloning, hours, and status updates
│   ├── gmail_api.py           # Email notifications
│   ├── oauth.py               # Google OAuth 2.0 flow & token management
│   └── twilio_api.py          # Twilio SMS dispatch & logging
├── scripts/
│   ├── run_calc.py            # CLI script for Monday morning calculations
│   └── run_send_texts.py      # CLI script for Monday noon SMS dispatches
│   └── tutoring.html          # Interactive HTML console & dark mode
├── tests/
│   ├── __init__.py            # Test package marker
│   ├── test_tutoring_calc.py  # Hours parsing, balances, and safeguards
│   ├── test_tutoring_apis.py  # Config, Twilio, Gmail, OAuth, Calendar, and Drive/Sheets helpers
│   └── test_tutoring_routes.py # Every HTTP endpoint (Google and Twilio mocked)
└── README.md                  # Module technical reference
```

---

## 5. Automated Testing

Run all unit tests for the Tutoring Calculator:

```bash
# From repository root
.venv/bin/python -m unittest discover -s modules/TutoringCalculator/tests -p "test_*.py"
```


Deeper documentation: [docs/TutoringCalculator/](../../docs/TutoringCalculator/)
