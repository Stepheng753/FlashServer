# Finance Module & Dashboard

The `Finance` package provides an interactive personal financial dashboard integrated with **SimpleFIN Bridge**, historical SQLite snapshots, time-series growth charts, credit utilization & rewards tracking, and net worth calculations.

Accessible at `http://localhost:5000/finance`.

---

## 1. Features & Architecture

* **SimpleFIN Bridge Open Banking Integration**: Connects seamlessly with SimpleFIN Bridge to ingest live balances from linked financial institutions.
* **SQLite Time-Series History Engine (`data/finance.db`)**: Stores point-in-time snapshots of Net Worth, Total Assets, Total Liabilities, Liquid Cash, Investments, and Debts with Write-Ahead Logging (`WAL`).
* **Interactive Growth & Amortization Visualizations**: Chart.js dynamic area and multi-line charts supporting timeframes (`1M`, `3M`, `6M`, `1Y`, `ALL`) and visualization modes:
  * **Net Worth Trajectory**: Historical progress towards debt freedom and wealth growth.
  * **Assets vs. Liabilities**: Comparative view of accumulated assets against mortgage & liabilities.
  * **Liquid vs. Invested Portfolio**: Breakdown between emergency liquidity and invested wealth.
* **Granular Account Categories**:
  * **Liquid Cash & HYSA**: Checking, high-yield savings, and operating cash.
  * **Credit Cards**: Revolving balances, credit utilization progress bar, and credit limits.
  * **Investments & Retirement**: Taxable brokerages, Roth/Traditional IRAs, and 401(k) plans with vested tracking.
  * **Real Estate & Loans**: Property valuation tracking and mortgage notes.
* **Direct Metadata & Notes Editor**: In-place modal to customize APY notes, status, holdings summary, and credit limits.
* **Shared Theme & Dark Mode**: Fully responsive, dark/light theme aware matching Crossroads / Flash Server Backend design tokens.

---

## 2. Endpoints Reference

All endpoints are protected by HTTP Basic Authentication.

### Web Dashboard
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/finance` | `GET` | Interactive Financial Dashboard UI. |

### Financial REST API
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /api/finance/summary` | `GET` | Returns calculated Net Worth, Total Assets, Liabilities, Liquid Cash, Investments, Debts, and categorized accounts. |
| `GET /api/finance/accounts` | `GET` | Returns all financial accounts with current balances, APY rates, and rewards metadata. |
| `GET /api/finance/history` | `GET` | Returns time-series snapshots for the interactive growth chart (`?timeframe=1m\|3m\|6m\|1y\|all`). |
| `POST /api/finance/sync` | `POST` | Triggers live balance sync from SimpleFIN Bridge and records a new historical snapshot. |
| `POST /api/finance/claim` | `POST` | Exchanges a one-time SimpleFIN claim token for an access URL or saves an access URL directly. |
| `GET /api/finance/settings` | `GET` | Returns SimpleFIN connection status, masked access URL, and last sync timestamp. |
| `POST /api/finance/disconnect` | `POST` | Clears SimpleFIN credentials. |
| `POST /api/finance/account/<id>` | `POST` | Updates editable account metadata, notes, credit limits, or manual balances. |
| `GET /api/finance/budget` | `GET` | Budget summary with income and expense items (see `docs/Finance/architecture.md`). |
| `POST /api/finance/budget/item` | `POST` | Creates or updates a budget item. |
| `GET /api/finance/budget/item/<id>` | `GET` | Returns one budget item with its `details`. |
| `DELETE /api/finance/budget/item/<id>` | `DELETE` | Deletes a budget item. |
| `POST /api/finance/budget/toggle/<id>` | `POST` | Toggles a budget item active / inactive. |
| `POST /api/finance/account/add` | `POST` | Creates a manual account (property, notes, crypto). |
| `DELETE /api/finance/account/<id>` | `DELETE` | Deletes an account and its history. |
| `POST /api/finance/deduplicate` | `POST` | Merges duplicate accounts. |
| `GET/POST /api/finance/settings/order` | `GET`/`POST` | Reads or saves the custom account order per category. |

---

## 3. Package Structure

```
Finance/
├── __init__.py                # Blueprint export (finance_bp)
├── config.py                  # Paths, SimpleFIN setting keys, secret helpers
├── db.py                      # SQLite WAL schema, accounts, snapshots, budget
├── simplefin_client.py        # Claim exchange, account matching, sync
├── routes.py                  # Web & REST API endpoints
├── finance.html               # Dashboard UI (Chart.js)
├── tests/
│   ├── __init__.py            # Test package marker
│   └── test_finance.py        # DB, maths, routes, and mocked SimpleFIN sync tests
└── README.md                  # Module technical reference
```

---

## 4. Automated Testing

```bash
# From repository root
.venv/bin/python -m unittest discover -s modules/Finance/tests -p "test_*.py"
```

Tests use a temporary database and never touch `data/finance.db`. More detail: [docs/Finance/](../../docs/Finance/architecture.md).
