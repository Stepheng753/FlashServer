<div align="center">

<img src="index/static/flash.gif" alt="Flash Server" width="200" style="border-radius: 12px; margin-bottom: 16px;" />

# ⚡ Flash Server
**Centralized Infrastructure API, System Telemetry & Operational Automation Hub**

[![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)](/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![ReportLab](https://img.shields.io/badge/ReportLab-4.4-FF6F00?style=for-the-badge&logo=python&logoColor=white)](https://www.reportlab.com/)
[![Swagger](https://img.shields.io/badge/OpenAPI-3.0-85EA2D?style=for-the-badge&logo=swagger&logoColor=black)](http://localhost:5000/docs)
[![Tailscale](https://img.shields.io/badge/Tailscale-Mesh-4E5EE4?style=for-the-badge&logo=tailscale&logoColor=white)](https://tailscale.com/)

*Flash Server is the production API engine, system telemetry monitor, and automation hub for Stephen Giang's infrastructure (`flash-server` at `dev.stepheng753.com`).*

---

</div>

## 📑 Table of Contents

- [🌟 Core Identity & Architecture](#-core-identity--architecture)
- [🛠️ Technology Stack](#️-technology-stack)
- [🏗️ Repository Structure](#️-repository-structure)
- [🖥️ System Monitoring Module](#️-system-monitoring-module)
- [🎓 Tutoring Calculator Automation](#-tutoring-calculator-automation)
- [📝 To-Do Task Management Module](#-to-do-task-management-module)
- [📄 Vector Invoice Generator Module](#-vector-invoice-generator-module)
- [🧪 Testing & Quality Assurance](#-testing--quality-assurance)
- [📚 Project Documentation](#-project-documentation)
- [🔗 Internal Module References](#-internal-module-references)
- [🔐 Configuration & Secrets](#-configuration--secrets)
- [🚀 Local Development & Execution](#-local-development--execution)
- [⚙️ CI/CD Deployment & Cron Schedules](#️-cicd-deployment--cron-schedules)

---

## 🌟 Core Identity & Architecture

`Flash Server` provides centralized operational intelligence and business automation across Stephen Giang's homelab server (`flash-server`). It bridges public web requests, containerized microservices, Google Cloud workspace tools, and communication APIs into a unified platform.

```
[Public Web / Clients] ───> https://dev.stepheng753.com
                                   │
                                   ▼
                       [Nginx Reverse Proxy]
                      Terminates Let's Encrypt SSL
                                   │
                     (unix:/tmp/dev_stepheng753_com_api.sock)
                                   │
                                   ▼
                       [Gunicorn WSGI / Flask]
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
  [Monitoring BP]           [Tutoring Calc BP]         [Swagger / OpenAPI]
  - Host Telemetry          - Calendar Scraper         - Interactive UI
  - Process Matrix          - Google Sheets Invoicing  - Basic Auth Security
  - 11-Service Probes       - Twilio SMS Reminders     - API Documentation
         │                         │
         ▼                         ▼
   [ToDo Board BP]          [Invoice Generator BP]
   - Categorized Board      - Pure-Python Vector PDFs
   - Drag-and-Drop Order    - Multi-Sender Profiles
   - Task Archival          - Client Presets & History
```

### 💼 Operational Philosophy
- **Lightweight & High-Performance:** Pure Python 3.12 with minimal dependencies; non-blocking telemetry collectors prevent event loop stalls.
- **Fail-Safe Business Logic:** Financial invoicing utilizes human-in-the-loop validation (`CALCULATED` title safeguard) before dispatching client notifications.
- **Zero Disk Leakage for PDFs:** Pure-Python vector PDF generation streamed in-memory via `io.BytesIO`. Zero PDF files are stored on disk.
- **Zero Polling & Thread Safety:** Concurrent threaded socket probes evaluate service uptime in parallel with 0.5s tight timeouts.
- **Secure Encrypted Transport:** Tailscale mesh network for automated CI/CD deployments and internal administration.

---

## 🛠️ Technology Stack

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12"/>
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask"/>
  <img src="https://img.shields.io/badge/ReportLab-FF6F00?style=for-the-badge&logo=python&logoColor=white" alt="ReportLab"/>
  <img src="https://img.shields.io/badge/SQLite3-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite3 WAL"/>
  <img src="https://img.shields.io/badge/Gunicorn-499848?style=for-the-badge&logo=gunicorn&logoColor=white" alt="Gunicorn"/>
  <img src="https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white" alt="Nginx"/>
  <img src="https://img.shields.io/badge/Let's_Encrypt-003A70?style=for-the-badge&logo=letsencrypt&logoColor=white" alt="Certbot"/>
  <img src="https://img.shields.io/badge/Google_Cloud-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white" alt="Google Cloud APIs"/>
  <img src="https://img.shields.io/badge/Twilio-F22F46?style=for-the-badge&logo=twilio&logoColor=white" alt="Twilio SMS"/>
  <img src="https://img.shields.io/badge/Tailscale-4E5EE4?style=for-the-badge&logo=tailscale&logoColor=white" alt="Tailscale"/>
  <img src="https://img.shields.io/badge/Ubuntu_24.04-E95420?style=for-the-badge&logo=ubuntu&logoColor=white" alt="Ubuntu Server"/>
</p>

### Key Capabilities
1. **Host & Container Telemetry:** Real-time metrics on 12-thread CPU loads, package thermals, DDR4 RAM utilization, NVMe & 32TB HDD array storage pools, and top processes.
2. **Automated Weekly Billing Pipeline:** Parses Google Calendar events for tutoring hours, computes rollover balances, generates structured Google Sheets invoices, and dispatches customized SMS payment texts via Twilio.
3. **Task Management & Archival:** Eisenhower-categorized To-Do board with drag-and-drop reordering, SQLite WAL persistence, and on-demand archival of completed tasks.
4. **Vector PDF Invoice Generator:** Full multi-profile invoice creator with in-memory ReportLab Platypus rendering, client service presets, dynamic filter metrics, and phone normalization.
5. **Interactive Developer Experience:** Built-in Swagger UI conforming to OpenAPI 3.0 specifications with HTTP Basic Authentication.

---

## 🏗️ Repository Structure

| Directory / File | Description | Environment / Port |
| :--- | :--- | :--- |
| **[`app.py`](./app.py)** | Main Flask application entry point with blueprint registrations. | `localhost:5000` / Unix Socket |
| **[`modules/Monitor/`](./modules/Monitor/)** | System telemetry collectors (`collectors/`), process monitors, service probes, and HTML dashboard. | `/monitoring` |
| **[`modules/TutoringCalculator/`](./modules/TutoringCalculator/)** | Weekly invoicing engine, web dashboard (`/tutoring`), Google APIs integration, and Twilio SMS client. | `/tutoring`, `/api/tutoring/*` |
| **[`modules/ToDo/`](./modules/ToDo/)** | Categorized task board, drag-and-drop reordering, and one-click archival of completed tasks. | `/todo`, `/api/todo/*` |
| **[`modules/InvoiceGenerator/`](./modules/InvoiceGenerator/)** | In-memory vector PDF invoice builder, client presets, multi-sender directory, and history tracker. | `/invoices`, `/api/invoices/*` |
| **[`modules/Finance/`](./modules/Finance/)** | Personal financial dashboard with SimpleFIN Bridge, SQLite history, and interactive growth charts. | `/finance`, `/api/finance/*` |
| **[`modules/Swagger/`](./modules/Swagger/)** | Interactive OpenAPI 3.0 Swagger documentation console and JSON spec generator. | `/`, `/docs`, `/openapi.json` |
| **[`index/`](./index/)** | HTTP Basic Auth middleware, security checkers, and route protection decorators. | Application middleware |
| **[`config/`](./config/)** | Environment configuration files and secret schemas. | Application configuration |
| **[`data/`](./data/)** | Gitignored SQLite databases (`tasks.db`, `invoices.db`, `finance.db`). | Runtime data |
| **[`index/`](./index/)** | Auth middleware (`index.py`), shared privacy page, and static assets (`index/static/`: `shared.css`, `flash.png`, `flash.gif`). | `/static/*`, `/privacy` |
| **[`docs/`](./docs/)** | Comprehensive setup runbooks, monitoring architecture, and billing guides. | Documentation repository |

---

## 🖥️ System Monitoring Module

Accessible at `http://localhost:5000/monitoring` (or `https://dev.stepheng753.com/monitoring`), the web dashboard provides live visibility into `flash-server` health:

* **Top 10 Processes Table**: Real-time process listing with interactive **Sort by RAM** and **Sort by CPU** toggles, user badges, and memory metrics.
* **Storage Devices & Mounts**: Live capacity and usage tracking across all 5 flash-server storage pools (`/`, `Dragon-Ball`, `Photos`, `CapCut-Videos`, `TV-Series`).
* **Services Matrix**: Multi-threaded socket probes verifying uptime for 11 critical homelab services (`Immich`, `Jellyfin`, `qBittorrent`, `Gluetun`, `n8n`, `PostgreSQL`, `AIU`, `Flash Server`, `Nginx`, `Samba`, `Tailscale`).
* **Diagnostic Audit Suite**: One-click modal audit testing disk space, RAM pressure, CPU thermals, and background cron log freshness.
* **Unified Dark Mode**: Defaults to system color scheme with manual toggle button.

### Monitoring Endpoints
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/monitoring` | `GET` | Interactive Swagger-styled HTML Web Dashboard. |
| `/api/monitoring/system` | `GET` | Live CPU load %, core count, thermals, RAM, swap, and host specifications. |
| `/api/monitoring/processes` | `GET` | Top processes sorted by RAM or CPU utilization (`?sort=ram|cpu&limit=10`). |
| `/api/monitoring/storage` | `GET` | Partition and network share storage capacities, free space, and warning thresholds. |
| `/api/monitoring/services` | `GET` | Real-time health statuses and latency metrics for all 11 monitored services. |
| `/api/monitoring/diagnostics` | `GET` | Itemized audit report across disks, memory, thermals, services, and cron logs. |

---

## 🎓 Tutoring Calculator Automation

Accessible at `http://localhost:5000/tutoring` (or `https://dev.stepheng753.com/tutoring`), the web console provides one-click triggers, Google Sheet links, earnings modal summaries, text message audit logs, and direct access to the Google Drive Pay folder.

Weekly billing cycle runs Monday–Sunday:

```
Monday 04:00 AM PST ───> curl -u "$USER:$PASS" -X POST /api/tutoring/run-calc
                               │
                [Human Review Window: 8 Hours]
                               │
Monday 12:00 PM PST ───> curl -u "$USER:$PASS" -X POST /api/tutoring/run-send-texts
```

### Tutoring Calculator Endpoints
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/tutoring` | `GET` | Interactive HTML Web Dashboard with one-click actions, modals, and dark mode. |
| `/api/tutoring/status` | `GET` | Live billing dates, Google auth state, current week sheet metadata, and Drive folder links. |
| `/api/tutoring/run-calc` | `POST` | One-click full pay calculation: clones template, scrapes hours, checks balances, updates sheet, and emails summary. |
| `/api/tutoring/run-send-texts` | `POST` | One-click SMS dispatch: evaluates `CALCULATED` title safeguard, sends Twilio texts, and updates statuses. |
| `/api/tutoring/dates` | `GET` | Computes preceding Monday & following Sunday billing week dates (`MM.DD.YY`). |
| `/api/tutoring/copy-template` | `POST` | Clones master template into target year folder named `MM.DD.YY - MM.DD.YY CALCULATED`. |
| `/api/tutoring/calc-hours` | `GET` | Scrapes Google Calendar for sessions ending in "Tutoring" and consolidates hours. |
| `/api/tutoring/previous-balances` | `GET` | Queries prior week's sheet for students marked `"Need to Pay"`. |
| `/api/tutoring/update-sheet` | `POST` | Injects hours into Column D, unpaid balances into Column G, and sends notification email. |
| `/api/tutoring/send-texts` | `POST` | Low-level text dispatch route guarded by `CALCULATED` approval check. |
| `/api/tutoring/text-logs` | `GET` | Returns raw audit log of all dispatched text messages (`text_messages.log`). |
| `/login_oauth` | `GET` | Google OAuth 2.0 web consent flow for Calendar, Drive, Sheets, and Gmail scopes. |

---

## 📝 To-Do Task Management Module

Accessible at `http://localhost:5000/todo`, the To-Do module provides category-based task organization with drag-and-drop sequencing and on-demand archival.

* **Eisenhower Categories**: Dynamic, color-accented category cards with live task counters.
* **Drag-and-Drop Reordering**: Immediate DOM reordering with background persistence to SQLite sort indices.
* **Task Archival**: Completed tasks are archived on demand (`POST /api/todo/archive-completed`), keeping active boards focused while preserving full historical records.
* **Archival Management**: One-click "Archive Completed", full category archival, and conflict-checked restoration.

### To-Do Endpoints
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/todo` | `GET` | Interactive To-Do board interface. |
| `GET /api/todo/items` | `GET` | Fetches active or archived tasks (`?status=active|archived`). |
| `POST /api/todo/items` | `POST` | Adds a task to a category (automatically placed above completed items). |
| `PATCH /api/todo/items/<id>` | `PATCH` | Updates task text, category, completion state, day tag, or size tag. |
| `DELETE /api/todo/items/<id>` | `DELETE`| Permanently deletes an individual task. |
| `POST /api/todo/reorder` | `POST` | Persists reordered task order within a category. |
| `POST /api/todo/archive-completed` | `POST`| Archives all completed tasks immediately. |
| `POST /api/todo/items/<id>/restore` | `POST`| Restores an archived task back to the active board. |
| `GET /api/todo/categories` | `GET` | Lists all active categories. |
| `POST /api/todo/categories` | `POST` | Creates a new category with duplicate-name detection. |
| `PATCH /api/todo/categories/<id>` | `PATCH` | Updates category name, color theme, status text, or sort order. |
| `POST /api/todo/categories/<id>/archive` | `POST`| Archives category and all associated tasks. |
| `POST /api/todo/categories/<id>/restore` | `POST`| Restores an archived category. |

See [`modules/ToDo/README.md`](modules/ToDo/README.md) for the complete list.

--- | :--- | :--- |
| `/todo` | `GET` | Interactive To-Do board interface. |
| `GET /api/tasks` | `GET` | Fetches active or archived tasks (`?status=active|archived`). |
| `POST /api/tasks` | `POST` | Adds a task to a category (automatically placed above completed items). |
| `PUT /api/tasks/<id>` | `PUT` | Updates task text, category, priority, due date, or completion state. |
| `DELETE /api/tasks/<id>` | `DELETE`| Permanently deletes an individual task. |
| `POST /api/tasks/reorder` | `POST` | Persists reordered task order within a category. |
| `POST /api/tasks/archive-completed` | `POST`| Archives all completed tasks immediately. |
| `POST /api/tasks/<id>/restore` | `POST`| Restores an archived task back to the active board. |
| `GET /api/categories` | `GET` | Lists all active categories with task counts. |
| `POST /api/categories` | `POST` | Creates a new category with duplicate-name detection. |
| `PUT /api/categories/<id>` | `PUT` | Updates category name, color theme, or sort order. |
| `DELETE /api/categories/<id>` | `DELETE`| Deletes category and cascades deletion to tasks. |
| `POST /api/categories/<id>/archive` | `POST`| Archives category and all associated tasks. |
| `POST /api/categories/<id>/restore` | `POST`| Restores an archived category and its tasks. |

---

## 📄 Vector Invoice Generator Module

Accessible at `http://localhost:5000/invoices` (or `/InvoiceGenerator/invoices`), the Invoice Generator produces professional, vector-sharp PDFs rendered on-demand in pure Python without writing files to disk.

* **In-Memory ReportLab Platypus Generation**: Fast, pure-Python PDF rendering (`io.BytesIO`). Zero disk files created.
* **PDF Title & Phone Normalization**: Automatically sets the internal PDF `/Title` metadata to `Invoice# - {Client Name}` and normalizes phone numbers to `+1 (XXX) XXX-XXXX`.
* **Selective Status Display**: The PDF header only displays the status if marked **`paid`** (in emerald green). Draft, sent, overdue, and void invoices remain clean for clients.
* **Client Service Presets**: Save line items, default due date offsets, discount amounts, tax rates, payment instructions, and terms for any client, and apply them with one click.
* **Live History Filter Metrics**: Real-time summary cards (Total Invoiced, Outstanding Balance, Total Collected, Total Clients) update immediately when changing filters.
* **Print Preview**: Dedicated print page (`/invoices/<id>/preview`) with `@media print` CSS, native print dialog, and direct PDF download.

### Invoice Generator Endpoints
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/invoices` | `GET` | Main invoice application dashboard. |
| `/invoices/<id>/preview` | `GET` | Print-ready HTML preview page with print toolbar. |
| `GET /api/invoices/summary` | `GET` | Dynamic summary metrics filtered by `status`, `client_id`, `sender_id`, `search`, etc. |
| `GET /api/invoices/next-number` | `GET` | Next sequential invoice number (`INV-YYYY-001`). |
| `GET /api/invoices` | `GET` | Lists invoices matching active filters. |
| `POST /api/invoices` | `POST` | Creates a new invoice with itemized line items. |
| `GET /api/invoices/<id>` | `GET` | Returns full invoice details and line items. |
| `PUT /api/invoices/<id>` | `PUT` | Updates an existing invoice. |
| `PATCH /api/invoices/<id>/status` | `PATCH` | Updates status (`draft`, `sent`, `paid`, `overdue`, `void`). |
| `POST /api/invoices/<id>/duplicate`| `POST` | Clones an invoice with a new invoice number in draft status. |
| `DELETE /api/invoices/<id>` | `DELETE`| Deletes an invoice and cascades to line items. |
| `GET /api/invoices/<id>/pdf` | `GET` | Streams the vector PDF directly to the browser. |
| `GET /api/invoices/senders` | `GET` | Lists all sender profiles. |
| `POST /api/invoices/senders` | `POST` | Creates a sender profile. |
| `GET /api/invoices/clients` | `GET` | Lists all clients. |
| `POST /api/invoices/clients` | `POST` | Creates a new client profile. |
| `GET /api/invoices/clients/<id>/presets` | `GET`| Retrieves saved service presets for a client. |
| `POST /api/invoices/presets` | `POST` | Saves a new preset with line items, invoice details, and terms. |

---

## 🧪 Testing & Quality Assurance

All test suites are organized into dedicated `tests/` directories within each module:

```
├── modules/InvoiceGenerator/tests/
│   ├── test_invoices.py       # DB, CRUD, calculations, and vector PDF bytes
│   ├── test_integration.py    # Flask route registration and OpenAPI verification
│   └── test_invoice_isolated.py # Calculations, filters, recurring schedules, all routes (temp DB)
├── modules/ToDo/tests/
│   ├── test_todo.py           # Task/category CRUD, reordering, tags, and manual archival
│   └── test_todo_isolated.py  # Ordering rules, validation, migrations, all routes (temp DB)
├── modules/TutoringCalculator/tests/
│   ├── test_tutoring_calc.py  # Hours parsing, calendar scraping, and safeguards
│   ├── test_tutoring_apis.py  # Config, Twilio, Gmail, OAuth, Calendar, Drive/Sheets helpers
│   └── test_tutoring_routes.py # Every HTTP endpoint (Google and Twilio mocked)
└── modules/Monitor/tests/
    ├── test_monitoring.py     # Smoke tests against the live host
    └── test_monitor_logic.py  # Mocked collectors, probes, diagnostics verdicts, routes
```

### Run All Tests Across the Repository
```bash
# Discover and run all 36+ automated tests
.venv/bin/python -m unittest discover -s . -p "test_*.py"
```

### Run Tests
```bash
# Every module at once
.venv/bin/python -m unittest discover -s modules -t . -p "test_*.py"

# One module (Finance, InvoiceGenerator, Monitor, Swagger, ToDo, TutoringCalculator)
.venv/bin/python -m unittest discover -s modules/Finance/tests -p "test_*.py"
```

Per-module notes on what each suite covers, and which ones touch the real databases, are in `docs/<Module>/testing.md`.

---

## 📚 Project Documentation

Explore the following modular documentation files for end-to-end setup and architecture details:

### 🛠️ Infrastructure & Web Deployment (`docs/setup/`)
* **[Server Hardware & Environment Setup](docs/setup/server.md)** — Host machine provisioning (Ubuntu 24.04 LTS, UFW firewall, Docker CE, Node.js, Python, storage mounts, systemd timers).
* **[Website & Nginx Projects Deployment](docs/setup/website.md)** — Nginx reverse proxy configurations, PM2 process management, Docker web containers, and Python WSGI socket deployment.
* **[Hostinger DNS & Certbot SSL Guide](docs/setup/dns-and-ssl.md)** — Hostinger DNS CNAME configuration, TP-Link Deco DDNS routing, router port forwarding, and automated Let's Encrypt SSL.
* **[Nginx Template Configuration](docs/setup/nginx.conf.template)** — Production-tested Nginx reverse-proxy template blocks (Unix socket, static + API, and local port).
* **[Setup Reference Specification](docs/setup/setup.conf)** — Master network configuration and subdomain routing definitions.

### 🖥️ Monitor (`docs/Monitor/`)
* **[Architecture & Endpoints](docs/Monitor/architecture.md)** — Non-blocking telemetry collectors, multi-threaded socket probes, memory/CPU metrics, and REST API specification.
* **[Services Matrix & Probes](docs/Monitor/services-matrix.md)** — The 11 monitored services, port mappings, and alert thresholds.
* **[Dashboard Operations Guide](docs/Monitor/dashboard-guide.md)** — Visual design guide, process table sort controls, refresh intervals, and diagnostic audit suite usage.
* **[Testing](docs/Monitor/testing.md)**

### 🎓 TutoringCalculator (`docs/TutoringCalculator/`)
* **[Billing Workflow & Endpoints](docs/TutoringCalculator/billing-workflow.md)** — Weekly billing cycle, calendar scraping mechanics, rate lookups, and spreadsheet updates.
* **[Approval Safeguards & SMS Text Dispatch](docs/TutoringCalculator/approval-safeguard.md)** — Human-in-the-loop review, `CALCULATED` title safety gate, Twilio SMS dispatch, and audit logging.
* **[Automation & Google OAuth 2.0 Setup](docs/TutoringCalculator/automation-and-oauth.md)** — Crontab schedules and Google OAuth 2.0 token management.
* **[Testing](docs/TutoringCalculator/testing.md)**

### ✅ ToDo (`docs/ToDo/`)
* **[Architecture](docs/ToDo/architecture.md)** — Data model, ordering rules, archiving behavior, categories, and tags.
* **[Testing](docs/ToDo/testing.md)**

### 🧾 InvoiceGenerator (`docs/InvoiceGenerator/`)
* **[Architecture](docs/InvoiceGenerator/architecture.md)** — Invoice lifecycle, totals, profiles, and presets.
* **[Recurring Invoices](docs/InvoiceGenerator/recurring-invoices.md)** — Schedule types, idempotency, and the daily cron run.
* **[Testing](docs/InvoiceGenerator/testing.md)**

### 💰 Finance (`docs/Finance/`)
* **[Architecture](docs/Finance/architecture.md)** — Schema, account types, snapshots and history, manual accounts, budget, and secrets.
* **[SimpleFIN Connection & Sync](docs/Finance/simplefin-sync.md)** — Claim flow, account matching, and balance change tracking.
* **[Testing](docs/Finance/testing.md)**

### 📖 Swagger (`docs/Swagger/`)
* **[Overview](docs/Swagger/overview.md)** — Routes, how the spec is maintained, and known documentation gaps.
* **[Testing](docs/Swagger/testing.md)**

---

## 🔗 Internal Module References

Each package maintains its own internal technical README:
* **[Invoice Generator](modules/InvoiceGenerator/README.md)** — Vector PDF Platypus architecture, database schema, presets, and route reference.
* **[Finance](modules/Finance/README.md)** — SimpleFIN Bridge integration, SQLite history engine, net worth tracking, and growth charts.
* **[To-Do](modules/ToDo/README.md)** — Category schema, task ordering, drag-and-drop indexing, and endpoints.
* **[Tutoring Calculator](modules/TutoringCalculator/README.md)** — Google Drive/Sheets integration, calendar hour parsing, and Twilio SMS safeguards.
* **[Monitor](modules/Monitor/README.md)** — Telemetry package, collector functions, process table sort controls, and the dashboard.
* **[Swagger](modules/Swagger/README.md)** — OpenAPI 3.0 specification and Swagger UI console.
* **[Index & Security](index/README.md)** — HTTP Basic Authentication middleware, secret credentials resolution, and path whitelist rules.

---

## 🔐 Configuration & Secrets

Configuration parameters and secret credentials are kept strictly isolated:

1. **`config/config.json`** *(Ignored by Git)*:
   * Stores deployment folder IDs, Google Calendar ID, Twilio Account SID, Twilio API Key SID, sender phone number, notification email, and host URL.
   * Blueprint tracked in **`config/config.template.json`** for initial setup.
2. **`config/secrets.json`** *(Ignored by Git)*:
   * Stores Swagger Basic Auth credentials (`USERNAME` / `PASSWORD`) and `TWILIO_API_SECRET`.
3. **`config/StephenG753-OAuth.json`** *(Ignored by Git)*:
   * Client secret credentials file downloaded from Google Cloud Console.
4. **`modules/TutoringCalculator/keys/token.pickle`** *(Ignored by Git)*:
   * Serialized Google OAuth 2.0 offline access token and auto-refresh token.
5. **`data/tasks.db` & `data/invoices.db`** *(Ignored by Git)*:
   * Local SQLite Write-Ahead Logging databases for task management and invoice tracking.

---

## 🚀 Local Development & Execution

### 1. Environment Setup
```bash
# Clone and enter directory
cd /home/stepheng753/Development/FlashServer

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Running Locally
```bash
# Launch development server
python3 app.py
```
* The local server will be accessible at `http://localhost:5000`.
* Open `http://localhost:5000/docs` to view the interactive Swagger UI.
* Open `http://localhost:5000/monitoring` to view the real-time hardware telemetry dashboard.
* Open `http://localhost:5000/tutoring` to view the interactive Crossroads Tutoring Console.
* Open `http://localhost:5000/todo` to view the interactive To-Do Board.
* Open `http://localhost:5000/invoices` to view the Vector Invoice Generator.

---

## ⚙️ CI/CD Deployment & Cron Schedules

### Production Service Management (`flash-server`)
```bash
# Check service status
sudo systemctl status dev_stepheng753_com_api.service

# Restart application daemon
sudo systemctl restart dev_stepheng753_com_api.service

# Stream live production logs
sudo journalctl -u dev_stepheng753_com_api.service -f
```

### Automated Monday Crontab
On `flash-server`, schedule the automated billing workflow via `crontab -e`:
```bash
# 1. Weekly Pay Calculation: Monday 4:00 AM PST
0 4 * * 1 curl -sS -u "$USERNAME:$PASSWORD" -X POST https://dev.stepheng753.com/api/tutoring/run-calc >> /home/flash-server/Development/FlashServer/TutoringCalculator/logs/cron.log 2>&1

# 2. Text Message Dispatch Guarded by Approval: Monday 12:00 PM (Noon) PST
0 12 * * 1 curl -sS -u "$USERNAME:$PASSWORD" -X POST https://dev.stepheng753.com/api/tutoring/run-send-texts >> /home/flash-server/Development/FlashServer/TutoringCalculator/logs/cron.log 2>&1
```

### Daily Recurring Invoices Crontab
Schedule the recurring invoices generator to check and generate scheduled invoices every day at 5:00 AM PST:
```bash
0 5 * * * curl -sS -u "$USERNAME:$PASSWORD" -X POST https://dev.stepheng753.com/api/invoices/recurring/run >> /home/flash-server/Development/FlashServer/InvoiceGenerator/logs/cron.log 2>&1
```

---

<div align="center">
  <i>Developed and engineered for Stephen Giang's Production Infrastructure</i>
</div>
