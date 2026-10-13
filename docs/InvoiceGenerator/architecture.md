# InvoiceGenerator Architecture

Source: [modules/InvoiceGenerator/](../../modules/InvoiceGenerator/). Overview, endpoint list and schema diagram: [module README](../../modules/InvoiceGenerator/README.md).

| File | Responsibility |
| :--- | :--- |
| `config.py` | `data/invoices.db` path and timezone. |
| `db.py` | Schema, migrations, senders, clients, presets, invoices, summaries, recurring generation. |
| `pdf.py` | `generate_invoice_pdf(invoice)`: ReportLab Platypus, returns a `BytesIO`. |
| `routes.py` | `invoice_bp` blueprint, registered at `/` and under `/InvoiceGenerator`. |
| `invoices.html` | Three-tab dashboard (Builder, History, Senders & Clients). |
| `invoice_print.html` | Print-ready preview at `/invoices/<id>/preview`. |

---

## 1. Invoice lifecycle

1. **Create** (`create_invoice`): the invoice number is generated when omitted, and the sender falls back to the first sender (the default sorts first). Line items without a description are skipped. A line amount is `quantity * unit_price`. `discount_amount` is subtracted from the subtotal, then `tax_rate` (a percentage, never negative) is applied to the discounted amount to give `total_amount`. Sender and client details are copied into `*_snapshot` columns so old invoices never change when a profile is edited.
2. **Number**: `generate_next_invoice_number()` returns `INV-<year>-NNN`, one higher than the largest sequence already used this year.
3. **Status**: `draft`, `sent`, `paid`, `overdue`, `void`, changed with `PATCH /api/invoices/<id>/status`.
4. **Duplicate**: copies an invoice into a new `draft` with the next number.
5. **Render**: `GET /api/invoices/<id>/pdf` streams the PDF from memory. Nothing is written to disk. Only `paid` invoices show their status in the PDF header.
6. **Delete**: removes the invoice and its line items (cascade).

`GET /api/invoices/summary` reports `total_invoiced`, `outstanding`, `paid` and `total_clients`, using the same filters as the list endpoint (`status`, `client_id`, `sender_id`, `search`, `start_date`, `end_date`).

---

## 2. Profiles and presets

* **Senders** hold the "from" details, payment instructions and default notes. One is marked as the default (`POST /api/invoices/senders/<id>/default`), and the default is the fallback sender for new and recurring invoices.
* **Clients** hold the "bill to" details.
* **Presets** belong to a client. They store line items (`items_json`), due-days offset, discount, tax rate, payment instructions and notes, and may be marked recurring. See [recurring-invoices.md](recurring-invoices.md).
* Phone numbers are normalized to `+1 (XXX) XXX-XXXX` by `format_phone()` in `db.py` and `pdf.py`.

---

## 3. Database

SQLite WAL at `data/invoices.db`, foreign keys on. Tables: `sender_profiles`, `clients`, `client_presets`, `invoices`, `invoice_items`. See the diagram in the module README. `init_db()` creates tables and applies column migrations on startup.
