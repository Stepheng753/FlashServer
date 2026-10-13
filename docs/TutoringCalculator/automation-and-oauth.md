# Tutoring Calculator Automation & Google OAuth 2.0 Setup

This document details the **automated cron job schedules** and the **Google OAuth 2.0 & Twilio credentials setup** powering the `TutoringCalculator` module.

---

## 1. Automated Cron Schedules & Endpoints

The tutoring billing pipeline runs on two scheduled HTTP endpoint triggers every Monday on the host machine (`flash-server`):

```
Monday 04:00 AM PST ───> curl -u "$USER:$PASS" -X POST /api/tutoring/run-calc
                               │
                [Human Review Window: 8 Hours]
                               │
Monday 12:00 PM PST ───> curl -u "$USER:$PASS" -X POST /api/tutoring/run-send-texts
```

### 1.1. Endpoint Execution Reference

#### `POST /api/tutoring/run-calc` (Action 1)
* **Endpoint**: `http://localhost:5000/api/tutoring/run-calc` (or `/tutoring/run-calc`)
* **Schedule**: Every Monday at `04:00 AM` PST
* **Responsibilities**:
  1. Computes preceding Monday–Sunday date range.
  2. Copies master template sheet into Google Drive target year folder (`PAY_PARENT_FOLDER_ID`).
  3. Titles the copy `MM.DD.YY - MM.DD.YY CALCULATED`.
  4. Scrapes Google Calendar for tutoring sessions and updates hours in Column D.
  5. Scrapes previous week's sheet for unpaid balances and updates Column G.
  6. Sends calculation summary email with direct spreadsheet link to `stepheng753@gmail.com`.
  7. Returns JSON with `sheet_url`, `total_balance`, and student breakdown for web UI and log tracking.

#### `POST /api/tutoring/run-send-texts` (Action 2)
* **Endpoint**: `http://localhost:5000/api/tutoring/run-send-texts` (or `/tutoring/run-send-texts`)
* **Schedule**: Every Monday at `12:00 PM` (Noon) PST
* **Responsibilities**:
  1. Locates the current week's sheet in Google Drive (auto-detected via date range).
  2. **Safeguard Check**: If title still contains `CALCULATED`, aborts immediately with `"status": "skipped"`.
  3. If approved (human deleted `CALCULATED`), iterates over students with balances and blank status.
  4. Sends SMS via Twilio API with invoice breakdown and payment details.
  5. Updates student status to `"Need to Pay"` in Column B.
  6. Appends audit log to `modules/TutoringCalculator/logs/text_messages.log`.
  7. Returns JSON with sent count, message details, and recent log lines.

---

### 1.2. Crontab Configuration on Production Server (`flash-server`)

Edit your server user's crontab on `flash-server`:
```bash
crontab -e
```

Add the following entries (using authenticated `curl` with your basic auth credentials):

```bash
# -----------------------------------------------------------------------------
# Crossroads Tutoring Weekly Automation Pipeline (Endpoint-Driven)
# -----------------------------------------------------------------------------
# 1. Weekly Pay Calculation: Monday 4:00 AM PST
0 4 * * 1 curl -sS -u "$USERNAME:$PASSWORD" -X POST https://dev.stepheng753.com/api/tutoring/run-calc >> /home/flash-server/Development/BackendServer/modules/TutoringCalculator/logs/cron.log 2>&1

# 2. Text Message Dispatch Guarded by Approval: Monday 12:00 PM (Noon) PST
0 12 * * 1 curl -sS -u "$USERNAME:$PASSWORD" -X POST https://dev.stepheng753.com/api/tutoring/run-send-texts >> /home/flash-server/Development/BackendServer/modules/TutoringCalculator/logs/cron.log 2>&1
```

> [!TIP]
> **Production Socket Alternative**: If you prefer triggering directly via the local Gunicorn socket without DNS/HTTPS routing:
> ```bash
> 0 4 * * 1 curl -sS -u "$USERNAME:$PASSWORD" --unix-socket /tmp/dev_stepheng753_com_api.sock -X POST http://localhost/api/tutoring/run-calc >> /home/flash-server/Development/BackendServer/modules/TutoringCalculator/logs/cron.log 2>&1
> 0 12 * * 1 curl -sS -u "$USERNAME:$PASSWORD" --unix-socket /tmp/dev_stepheng753_com_api.sock -X POST http://localhost/api/tutoring/run-send-texts >> /home/flash-server/Development/BackendServer/modules/TutoringCalculator/logs/cron.log 2>&1
> ```

> [!NOTE]
> `flash-server` is configured to Pacific Time (`America/Los_Angeles`), so standard cron times run natively in PST/PDT:
> * `0 4 * * 1` = 4:00 AM Pacific Time
> * `0 12 * * 1` = 12:00 PM (Noon) Pacific Time

---

## 2. Google OAuth 2.0 Token Lifecycle

`TutoringCalculator` accesses Google Drive, Sheets, Calendar, and Gmail using an OAuth 2.0 User Token (`token.pickle`).

### 2.1. Required Google API Scopes
The application requires the following scopes defined in `google_auth.py`:
* `https://www.googleapis.com/auth/calendar.readonly`: Reads tutoring event names and durations.
* `https://www.googleapis.com/auth/drive`: Creates year folders and copies template spreadsheets.
* `https://www.googleapis.com/auth/spreadsheets`: Reads and writes student hours, balances, and payment statuses.
* `https://www.googleapis.com/auth/gmail.send`: Sends notification emails to Stephen.

### 2.2. Initial OAuth Authorization Flow
1. Obtain the Google Client Secret JSON file from Google Cloud Console.
2. Save it to `config/StephenG753-OAuth.json` (configured in `config/config.json`).
3. Start the Backend Server:
   ```bash
   ./app.py
   ```
4. In a web browser, navigate to the authorization route:
   * Local WSL: `http://localhost:5000/TutoringCalculator/login_oauth`
   * Production: `https://dev.stepheng753.com/TutoringCalculator/login_oauth`
5. Sign in with the primary Google account (`stepheng753@gmail.com`) and click **Allow**.
6. The callback handler exchanges the authorization code for an **Access Token** and **Refresh Token**, and serializes them to:
   `modules/TutoringCalculator/keys/token.pickle`

### 2.3. Automatic Token Refresh
Whenever an API request is made:
1. `get_credentials()` loads `token.pickle`.
2. If the access token has expired (typically after 60 minutes), the library uses `creds.refresh(Request())` with the persistent refresh token.
3. The newly issued access token is saved back to `token.pickle` automatically. No manual intervention is needed.

> [!WARNING]
> If your Google Cloud project is in **"Testing"** publishing status, Google limits refresh token validity to **7 days**. Ensure your Google Cloud OAuth Consent Screen is published to **"Production"** or add your user email as a permanent test user to prevent weekly re-authorization.

---

## 3. Configuration & Secrets (`config.json` & `secrets.json`)

Configuration parameters are stored in `config/config.json` and sensitive tokens in `config/secrets.json`:

### `config/config.json`
```json
{
  "GOOGLE_CALENDAR_ID": "primary",
  "PAY_PARENT_FOLDER_ID": "12hcaaHrab8TCFO8hi_cC67FRBHIU-Xsx",
  "TEMPLATE_SHEET_ID": "1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA",
  "NOTIFICATION_EMAIL": "stepheng753@gmail.com",
  "APP_HOST": "localhost:5000",
  "OAUTH_FILE": "StephenG753-OAuth.json",
  "TWILIO_ACCOUNT_SID": "ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  "TWILIO_API_KEY_SID": "SKXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  "TWILIO_FROM_NUMBER": "+16195550100"
}
```

### `config/secrets.json`
```json
{
  "TWILIO_API_SECRET": "your_twilio_api_secret_here"
}
```
*(Ensure `secrets.json` is listed in `.gitignore` so tokens are never committed to version control).*
