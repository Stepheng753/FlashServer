# Crossroads Tutoring Billing Workflow & Endpoints

This document details the weekly automated billing calculation lifecycle, Google Calendar event parsing, and Google Sheets invoice population in the `TutoringCalculator` module.

---

## 1. Weekly Billing Lifecycle Overview

Crossroads Tutoring operates on a weekly billing cycle running from Monday to Sunday:

```
[Monday Morning 04:00 AM]
          │
          ▼
[1. Calculate Billing Dates (/api/tutoring/dates)]
  start_date (Previous Monday) ➔ end_date (Following Sunday)
          │
          ▼
[2. Copy Template Sheet (/api/tutoring/copy-template)]
  Copies master "Student Pay" into target Year Folder
  Renames to "MM.DD.YY - MM.DD.YY CALCULATED"
          │
          ▼
[3. Parse Calendar Hours (/api/tutoring/calc-hours)]
  Parses Google Calendar for default-colored events ending in "Tutoring"
  Consolidates hours by student first name
          │
          ▼
[4. Query Previous Unpaid Balances (/api/tutoring/previous-balances)]
  Inspects prior week's sheet for rows with status "Need to Pay"
          │
          ▼
[5. Update Sheet & Notify (/api/tutoring/update-sheet)]
  Populates Column D (Hours) and Column G (Remaining Balances)
  Sends email alert with spreadsheet link to Stephen Giang
```

---

## 2. Endpoints Technical Reference

### 2.1. `GET /api/tutoring/dates`
* **Purpose**: Calculates the billing week date range.
* **Logic**: Computes the previous Monday date (if today is Monday, calculates the previous Monday 7 days prior) and the following Sunday in `MM.DD.YY` and ISO format.
* **Response**:
  ```json
  {
    "start_date": "08.31.26",
    "end_date": "09.06.26",
    "start_date_full": "2026-08-31",
    "end_date_full": "2026-09-06"
  }
  ```

### 2.2. `POST /api/tutoring/copy-template`
* **Parameters** (JSON or query): `start_date`, `end_date` (optional; auto-computed if omitted).
* **Behavior**:
  1. Locates or creates a subfolder for the target year (e.g. `2026`) inside `PAY_PARENT_FOLDER_ID`.
  2. Copies the master `TEMPLATE_SHEET_ID`.
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

### 2.3. `GET /api/tutoring/calc-hours`
* **Parameters**: `start_date`, `end_date`
* **Behavior**:
  1. Queries Google Calendar API for events between `start_date 00:00:00` and `end_date 23:59:59` PST.
  2. Filters events where the last word of the title is `"Tutoring"` and `colorId` is default / primary.
  3. Aggregates total duration by student first name.
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

### 2.4. `GET /api/tutoring/previous-balances`
* **Parameters**: `start_date`, `end_date`
* **Behavior**:
  1. Locates the previous week's sheet (7 days prior to `start_date`).
  2. Scans student rows where `Student Status` (Column B) is `"Need to Pay"`.
  3. Returns a dictionary mapping student first names to their unpaid balance.

### 2.5. `POST /api/tutoring/update-sheet`
* **Parameters**:
  * `sheet_id`: Google Sheet ID (required).
  * `action`: `"update_hours"` or `"update_pay_status"`.
* **Behavior (`update_hours`)**:
  1. Matches student names from Row 5 down.
  2. Writes calculated tutoring hours to Column D.
  3. Writes previous unpaid balances to Column G.
  4. Halts processing before the summary / subtotal row.
  5. Sends an email notification to `NOTIFICATION_EMAIL` containing the sheet link.

### 2.6. `POST /api/tutoring/run-calc` (Orchestrator Endpoint)
* **Parameters**: `start_date`, `end_date` (optional, auto-calculated if omitted).
* **Behavior**:
  1. Automatically runs steps 2.1 through 2.5 in a single unified atomic workflow.
  2. Copies template into year folder titled `MM.DD.YY - MM.DD.YY CALCULATED`.
  3. Scrapes Google Calendar and updates spreadsheet cells.
  4. Sends email notification.
  5. Returns JSON response containing `sheet_id`, `sheet_url`, `sheet_title`, `total_balance`, and student list.
  6. Used by both the **`[⚡ Run Weekly Pay Calculation]`** web dashboard button and Monday morning automated crontab.

