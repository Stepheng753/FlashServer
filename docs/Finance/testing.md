# Finance Testing

Tests: [modules/Finance/tests/test_finance.py](../../modules/Finance/tests/test_finance.py)

```bash
.venv/bin/python -m unittest discover -s modules/Finance/tests -p "test_*.py"
```

## Isolation

Every database test patches `modules.Finance.db.DB_PATH` to a temporary file, so `data/finance.db` is never touched. The route tests use a minimal Flask app that only registers `finance_bp` (no auth), and patch `save_secret` so `config/secrets.json` is never written. Network calls to SimpleFIN (`requests.get` / `requests.post`) are mocked.

## Coverage

| Class | What it checks |
| :--- | :--- |
| `TestFinanceDb` | Schema creation and idempotent `init_db`, upsert and lookup, ordering, metadata updates, delete cascades (snapshots and account-order settings), settings, empty snapshot. |
| `TestFinanceSummaryAndHistory` | Net worth, assets, liabilities, equity and credit utilization maths. Snapshot-to-history agreement, `net_worth_change` carry-forward, timeframe filtering. |
| `TestBudget` | Create, update, toggle, delete, and the monthly summary (inactive items ignored, pre-tax / post-tax split). |
| `TestSimpleFinHelpers` | Claim token decoding, institution normalization, mask extraction, account type inference, ID-based matching. |
| `TestClaimAccessUrl` | Success, bad status, malformed body, and network failure. |
| `TestFinanceRoutes` | Dashboard page, empty-state endpoints, manual account add / update / delete with type normalization, order settings, budget endpoints, claim validation, settings masking, disconnect, baseline sync. |
| `TestSimpleFinSync` | Full sync against a mocked bridge: new accounts, matched account updates with balance change, mortgage sign flip, error handling. |

## Adding tests

Subclass `FinanceDbTestCase` to get a fresh temporary database in `setUp`. Use `make_account(...)` to build account dicts.
