# Approval Safeguards & SMS Text Dispatch

This document details the **human-in-the-loop approval mechanism**, the **`CALCULATED` title safety gate**, and the **Twilio SMS notification pipeline** in the `TutoringCalculator` module.

---

## 1. The Human-in-the-Loop Safeguard Architecture

Automated billing should never charge clients or dispatch text messages without human verification. To prevent erroneous messages (e.g., miscategorized calendar entries, adjusted student rates, or in-person cash payments):

```
                                [4:00 AM Cron POST /api/tutoring/run-calc]
                                              │
                                              ▼
                             [Sheet Created in Google Drive]
                          "08.31.26 - 09.06.26 CALCULATED"
                                              │
                                              ▼
                             [Email Notification Sent to Stephen]
                             Contains spreadsheet link & metrics
                                              │
                                              ▼
                                   [Manual Human Review]
                            Stephen verifies hours and balances
                                              │
                           ┌──────────────────┴──────────────────┐
                           │                                     │
                    [Changes Needed?]                    [Verified Correct]
                           │                                     │
              Edit numbers directly in sheet          Rename sheet title:
                           │                     Remove " CALCULATED"
                           └──────────────────┬──────────────────┘
                                              │
                                              ▼
                             [12:00 PM Cron POST /api/tutoring/run-send-texts]
                                              │
                         ┌────────────────────┴────────────────────┐
                         ▼                                         ▼
            Title contains "CALCULATED"?                Title has NO "CALCULATED"?
                         │                                         │
                 [ABORT DISPATCH]                          [PROCEED WITH SMS]
         Returns "status": "skipped"                Sends Twilio SMS to parents
         Zero messages dispatched                   Sets Status to "Need to Pay"
```

---

## 2. The `CALCULATED` Safety Gate

### 2.1. Generation Phase
When `POST /api/tutoring/run-calc` (or `POST /api/tutoring/copy-template`) creates a new spreadsheet, it appends the tag `CALCULATED` to the sheet title:
```
Title Format: MM.DD.YY - MM.DD.YY CALCULATED
Example:      08.31.26 - 09.06.26 CALCULATED
```

### 2.2. Human Verification Checklist
Stephen receives an automated email at 4:00 AM with the sheet link (or reviews it via the `/tutoring` dashboard). Before noon, perform the following verification:
1. **Check Student Hours (Column D)**: Confirm tutoring calendar events matched actual sessions.
2. **Review Hourly Rates (Column C)**: Confirm rates are accurate for individual students.
3. **Verify Previous Balances (Column G)**: Confirm rollover balances from prior unpaid weeks.
4. **Approve the Sheet**:
   * Click on the spreadsheet title at the top-left of Google Sheets.
   * Delete ` CALCULATED` from the title so it becomes:
     `08.31.26 - 09.06.26`

### 2.3. Safety Interception in Code
When `POST /api/tutoring/run-send-texts` (or `POST /api/tutoring/send-texts`) executes, it evaluates `get_pending_text_recipients()`:

```python
# modules/TutoringCalculator/apis/drive_sheets_api.py
if "CALCULATED" in sheet_title:
    return {
        "is_pending_review": True,
        "title": sheet_title,
        "message": "Sheet title contains 'CALCULATED'. SMS sending aborted until human review is complete.",
        "recipients": []
    }
```

If `CALCULATED` is present, the endpoint immediately returns `"status": "skipped"` with zero texts sent.

---

## 3. Twilio SMS Dispatch Rules

Once the sheet title is approved (i.e. `CALCULATED` is removed), `POST /api/tutoring/send-texts` parses student rows to identify eligible recipients.

### 3.1. Recipient Eligibility Criteria
A student row receives an SMS if and only if **all** of the following conditions are met:
1. **Total Balance > $0.00** (Column J).
2. **Payment Status is empty** (Column B is NOT `"Paid"` and NOT `"Need to Pay"`).
3. **Valid Phone Number** is present in Column K (E.164 formatted or 10-digit US number).

### 3.2. Personalized Message Template
Each message is dynamically constructed with student-specific details:

```text
Hi [Parent/Student Name], this is Stephen Giang from Crossroads Tutoring.
Here is the invoice summary for [Student Name] for the week of [Start Date] - [End Date]:
- Hours: [Hours] hrs @ $[Rate]/hr = $[Subtotal]
- Previous Balance: $[PrevBalance]
- Total Due: $[Total]

Payment options:
Venmo: @Stephen-Giang (4 digits: 0753)
Zelle: stepheng753@gmail.com

Thank you!
```

### 3.3. Post-Dispatch State Updates
Immediately following successful Twilio transmission:
1. **Spreadsheet Status Update**: Column B is updated from blank to `"Need to Pay"`.
2. **Timestamping**: Column L logs the transmission timestamp and Twilio Message SID.
3. **Local Audit Logging**: Details are written to `modules/TutoringCalculator/logs/text_messages.log`.

---

## 4. Audit Logging & Verification

### 4.1. Text Message Audit Log
All dispatched text messages are logged locally in `modules/TutoringCalculator/logs/text_messages.log`:
```
[2026-09-07 12:00:15 PST] SENT to Elijah (+16195550143) | SID: SM892a4f... | Balance: $180.00
[2026-09-07 12:00:18 PST] SENT to Ellie (+16195550198) | SID: SM719b2c... | Balance: $270.00
```

### 4.2. Querying Logs via API
View recent text logs directly via browser or curl:
```bash
curl -X GET http://localhost:5000/api/tutoring/text-logs
```
* **Endpoint**: `GET /api/tutoring/text-logs`
* **Content-Type**: `text/plain`
* **Response**: Raw contents of `text_messages.log`.

---

## 5. Manual Emergency Overrides

### How to Prevent Texts from Sending
If you do not want texts to send for a given week:
* Simply **do not remove `CALCULATED`** from the Google Sheet title.
* Or change individual student status (Column B) to `"Hold"` or `"Paid"`.

### How to Force a Resend
If a parent requests their invoice text again:
1. Clear Column B (Status) and Column L (Timestamp) for that student row in Google Sheets.
2. Call `POST /api/tutoring/send-texts?sheet_id=<SHEET_ID>`.
