# Flash Server Documentation

One folder per module, plus `setup/` for server and deployment runbooks. Each module's own reference (features, endpoint tables, package tree) lives in `modules/<Module>/README.md`. These folders hold the deeper material: architecture, workflows, and testing.

| Folder | Module | Documents |
| :--- | :--- | :--- |
| [Finance/](Finance/) | `modules/Finance` | [architecture](Finance/architecture.md), [simplefin-sync](Finance/simplefin-sync.md), [testing](Finance/testing.md) |
| [InvoiceGenerator/](InvoiceGenerator/) | `modules/InvoiceGenerator` | [architecture](InvoiceGenerator/architecture.md), [recurring-invoices](InvoiceGenerator/recurring-invoices.md), [testing](InvoiceGenerator/testing.md) |
| [Monitor/](Monitor/) | `modules/Monitor` | [architecture](Monitor/architecture.md), [services-matrix](Monitor/services-matrix.md), [dashboard-guide](Monitor/dashboard-guide.md), [testing](Monitor/testing.md) |
| [Swagger/](Swagger/) | `modules/Swagger` | [overview](Swagger/overview.md), [testing](Swagger/testing.md) |
| [ToDo/](ToDo/) | `modules/ToDo` | [architecture](ToDo/architecture.md), [testing](ToDo/testing.md) |
| [TutoringCalculator/](TutoringCalculator/) | `modules/TutoringCalculator` | [billing-workflow](TutoringCalculator/billing-workflow.md), [approval-safeguard](TutoringCalculator/approval-safeguard.md), [automation-and-oauth](TutoringCalculator/automation-and-oauth.md), [testing](TutoringCalculator/testing.md) |
| [setup/](setup/) | Host and deployment | [server](setup/server.md), [website](setup/website.md), [dns-and-ssl](setup/dns-and-ssl.md) |

## Running the tests

From the repository root:

```bash
# Everything
.venv/bin/python -m unittest discover -s modules -t . -p "test_*.py"

# One module
.venv/bin/python -m unittest discover -s modules/<Module>/tests -p "test_*.py"
```

Which suites use the real databases:

| Module | Tests that use the real database |
| :--- | :--- |
| Finance | None |
| ToDo | `test_todo.py` (`data/tasks.db`; `[TEST]` rows are cleaned up) |
| InvoiceGenerator | `test_invoices.py`, `test_integration.py` (`data/invoices.db`) |
| Monitor, Swagger, TutoringCalculator | None |

The other test files in ToDo and InvoiceGenerator use a temporary database.

## Measuring coverage

Coverage is not in `requirements.txt`. Install it into the virtualenv when you want a report:

```bash
.venv/bin/pip install coverage
.venv/bin/python -m coverage run --source=modules --omit="*/tests/*" -m unittest discover -s modules -t . -p "test_*.py"
.venv/bin/python -m coverage report --skip-empty
```

Current coverage by module: Monitor 94%, ToDo 94%, InvoiceGenerator 91%, TutoringCalculator 96%, Finance 78%, Swagger 89%.
