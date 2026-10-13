# InvoiceGenerator Testing

Tests: [modules/InvoiceGenerator/tests/](../../modules/InvoiceGenerator/tests/)

```bash
.venv/bin/python -m unittest discover -s modules/InvoiceGenerator/tests -p "test_*.py"
```

## `test_invoices.py` and `test_integration.py` (real database)

These use the real `data/invoices.db`. `test_invoices.py` covers sender, client and preset CRUD, the invoice lifecycle, PDF bytes, the REST API, and recurring generation; its tests are numbered because later ones build on earlier data. `test_integration.py` uses the real app (credentials from `config/secrets.json`) to check pages, the summary endpoint, and the OpenAPI listing. Avoid running them while you are entering real invoices.

## `test_invoice_isolated.py` (temporary database)

Patches `modules.InvoiceGenerator.db.DB_PATH` to a temporary file, so it never touches `data/invoices.db`. Routes use a Flask app that only registers `invoice_bp`.

| Class | What it checks |
| :--- | :--- |
| `TestFormatting` | Phone and currency formatting. |
| `TestSenders` | Seeded default sender, only one default at a time, setting a missing sender as default leaves the current default alone, phone normalization. |
| `TestInvoiceCalculations` | Totals with discount and tax, floors at zero, blank and malformed line items, sequential and custom numbers, snapshots survive profile edits, update recalculates, status validation, duplicate, delete cascade. |
| `TestInvoiceQueries` | Status, client, search and date filters, sorting (and an unsafe sort field), past-due invoices flagged overdue on read, summary totals including void. |
| `TestPresetsAndRecurring` | Monthly (day clamping), weekly and biweekly schedules, start date, same-day idempotency, `auto_status` / discount / tax carried into the invoice, non-recurring presets skipped, bad date string, preset CRUD and client cascade. |
| `TestInvoiceRoutes` | Pages and preview, every sender, client, preset and invoice endpoint with its 400 / 404 cases, recurring run via `GET`, `POST`, query and body, PDF download headers. |
| `TestPdfContent` | PDFs with many items, discount and tax, and missing optional fields. |

Note: `get_invoices` and `get_invoices_summary` change data. Any draft or sent invoice whose due date has passed is saved as `overdue` the next time either is called.
