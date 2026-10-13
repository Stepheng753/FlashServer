# Recurring Invoices

Source: `process_recurring_invoices()` in [modules/InvoiceGenerator/db.py](../../modules/InvoiceGenerator/db.py)

A preset with `is_recurring = 1` generates an invoice on schedule. Nothing in the app wakes up by itself: a daily cron job calls `POST /api/invoices/recurring/run`.

---

## 1. Schedule types

`recurrence_day` and `recurrence_start_date` are interpreted per `recurrence_type`:

| Type | `recurrence_day` | Due on |
| :--- | :--- | :--- |
| `monthly` | Day of month (1-31) | That day. Short months clamp, so day 31 runs on the 28th, 29th or 30th. |
| `weekly` | Weekday, `0` = Monday ... `6` = Sunday | Every matching weekday. |
| `biweekly` | Weekday, as above | Every other matching weekday, counted from the first matching weekday on or after `recurrence_start_date`. Without a start date, every matching weekday. |

If `recurrence_start_date` is set, nothing is generated before it.

---

## 2. What a run does

For the target date (`?date=YYYY-MM-DD`, default today in `America/Los_Angeles`; a bad date falls back to today):

1. Load every preset with `is_recurring = 1`.
2. Skip presets whose `last_generated_date` equals the target date. This makes repeated calls on the same day safe.
3. Skip presets that are not due, or whose client no longer exists.
4. Pick the preset's sender, or the first sender if that one is gone.
5. Create an invoice: next sequential number, `issue_date` = target date, `due_date` = target date + `default_due_days` (14 if unset), status from `auto_status` (`draft` by default), items, discount, tax, payment instructions and notes from the preset.
6. Set `last_generated_date` on the preset.

Response:

```json
{
  "success": true,
  "date": "2026-10-01",
  "active_recurring_presets": 3,
  "created_count": 1,
  "invoices": [ { "id": 12, "invoice_number": "INV-2026-012", "client_name": "Acme", "status": "draft" } ]
}
```

Both `GET` and `POST` are accepted on the route.

---

## 3. Cron

See the crontab lines in the [module README](../../modules/InvoiceGenerator/README.md#crontab-setup-on-linux-production-server-flash-server). To dry-run a past date: `curl -u "$USERNAME:$PASSWORD" -X POST "http://localhost:5000/api/invoices/recurring/run?date=2026-10-01"`. This really creates invoices, so delete them afterwards if it was only a test.

A missed day is not made up later. If the cron job did not run on a preset's due date, call the endpoint with that date manually.
