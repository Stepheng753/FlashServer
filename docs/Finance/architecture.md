# Finance Architecture

Source: [modules/Finance/](../../modules/Finance/). Overview and endpoint list: [module README](../../modules/Finance/README.md).

| File | Responsibility |
| :--- | :--- |
| `config.py` | Paths (`data/finance.db`, `config/secrets.json`), SimpleFIN setting keys, `get_secret` / `save_secret`. |
| `db.py` | SQLite schema, migrations, accounts, snapshots, summary, settings, budget. |
| `simplefin_client.py` | Claim-token exchange, account matching, and the sync routine. See [simplefin-sync.md](simplefin-sync.md). |
| `routes.py` | `finance_bp` blueprint. Calls `init_db()` at import time. |
| `finance.html` | Dashboard UI (Chart.js). |

---

## 1. Database (`data/finance.db`)

WAL mode, created and migrated by `init_db()` on import. `init_db()` is safe to run repeatedly: new columns are added with `ALTER TABLE` when missing, and a deduplication pass runs at the end.

| Table | Purpose |
| :--- | :--- |
| `accounts` | One row per account: institution, name, mask, `account_type`, `balance`, credit limit, vested balance, `is_asset`, `is_manual`, `simplefin_id`, plus `balance_change`, `prev_balance`, `balance_change_at`. |
| `snapshots` | Point-in-time totals (net worth, assets, liabilities, liquid cash, investments, mortgage debt, credit debt, `net_worth_change`). |
| `account_snapshots` | Per-account balance for each snapshot (cascades from `snapshots`). |
| `settings` | Key/value store: SimpleFIN URL and claim preview, last sync time, `account_order_<category>` JSON lists. |
| `budget_items` | Income and expense line items (see section 4). |

### Account types and how they are counted

| `account_type` | Counted as |
| :--- | :--- |
| `checking`, `savings` | Liquid cash (asset) |
| `investment`, `retirement` | Investments (asset, with optional `vested_balance`) |
| `property`, `real_estate` | Property value (asset) |
| `mortgage`, `loan` | Mortgage debt (liability, absolute value) |
| `credit` | Credit debt (liability, stored negative; also drives credit utilization) |

`net_worth = liquid_cash + investments + property - (mortgage_debt + |credit_debt|)`.
`home_equity = property_value - mortgage_debt` and `credit_utilization = |credit_debt| / total_credit_limit * 100`.

---

## 2. Snapshots and history

`record_snapshot()` totals every account and writes one `snapshots` row and one `account_snapshots` row per account. It returns `None` when there are no accounts. If no `net_worth_change` is passed, the previous snapshot's value is carried forward.

Snapshots are recorded by sync, by adding / editing / deleting an account, and by the "Pre-SimpleFIN baseline" sync.

`get_historical_snapshots(timeframe)` accepts `1m` (31 days), `3m` (92), `6m` (183), `1y` (366), or anything else for all history. When the rows span several days it keeps only the latest snapshot of each day and labels points `Mon DD, YYYY`. When they all fall on one day it keeps every point and labels them with the time.

---

## 3. Manual accounts

`POST /api/finance/account/add` creates accounts the bridge cannot see (property, private notes, crypto). The `account_type` you send is normalized:

| Input | Stored as | `is_asset` |
| :--- | :--- | :--- |
| `cash`, `savings` | `savings` | 1 |
| `checking` | `checking` | 1 |
| `credit`, `credit_card` | `credit` | 0 |
| `investment(s)`, `retirement` | `investment` | 1 |
| `property_mortgage`, `property`, `real_estate`, `mortgage`, `loan` | `mortgage` if balance < 0, else `property` | 0 / 1 |

IDs look like `manual_<slug>_<unix time>`. Editing an account re-applies the same rules, so flipping a property balance negative turns it into a mortgage.

---

## 4. Budget

`budget_items` rows have a `category` (`income` or `expense`), an `amount` normalized to monthly, an optional `raw_amount` and `frequency`, a `tax_status` (`pre-tax` / `post-tax`), and an optional `details_json` blob (for example a paystub breakdown, returned as `details`).

`get_budget_summary()` only counts active items:

* `total_monthly_income_posttax` / `total_monthly_income_pretax` / `total_income_combined`
* `total_monthly_expenses`
* `net_monthly_cash_flow = post-tax income - expenses`

---

## 5. Secrets

The SimpleFIN access URL contains credentials, so it is saved to `config/secrets.json` (gitignored) under `SIMPLEFIN_ACCESS_URL`, and mirrored into the `settings` table. `get_stored_access_url()` checks `secrets.json` first. `GET /api/finance/settings` only returns a masked URL (`https://***:***@host/path`).
