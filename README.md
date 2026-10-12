<div align="center">

<img src="static/flash.gif" alt="Flash Server" width="200" style="border-radius: 12px; margin-bottom: 16px;" />

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
   - Monday 2 AM Archive    - Client Presets & History
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
3. **Task Management & Automated Archival:** Eisenhower-categorized To-Do board with drag-and-drop reordering, SQLite WAL persistence, and a background daemon that archives completed tasks Mondays @ 2:00 AM PST.
4. **Vector PDF Invoice Generator:** Full multi-profile invoice creator with in-memory ReportLab Platypus rendering, client service presets, dynamic filter metrics, and phone normalization.
5. **Interactive Developer Experience:** Built-in Swagger UI conforming to OpenAPI 3.0 specifications with HTTP Basic Authentication.

---

## 🏗️ Repository Structure

| Directory / File | Description | Environment / Port |
| :--- | :--- | :--- |
| **[`app.py`](./app.py)** | Main Flask application entry point with blueprint registrations. | `localhost:5000` / Unix Socket |
| **[`Monitoring/`](./Monitoring/)** | System telemetry collectors (`collectors/`), process monitors, service probes, and HTML dashboard. | `/monitoring` |
| **[`TutoringCalculator/`](./TutoringCalculator/)** | Weekly invoicing engine, web dashboard (`/tutoring`), Google APIs integration, and Twilio SMS client. | `/tutoring`, `/api/tutoring/*` |
| **[`ToDo/`](./ToDo/)** | Categorized task board, drag-and-drop reordering, and Monday 2:00 AM PST auto-archive scheduler. | `/todo`, `/api/tasks`, `/api/categories` |
| **[`InvoiceGenerator/`](./InvoiceGenerator/)** | In-memory vector PDF invoice builder, client presets, multi-sender directory, and history tracker. | `/invoices`, `/api/invoices/*` |
| **[`Finance/`](./Finance/)** | Personal financial dashboard with SimpleFIN Bridge, SQLite history, and interactive growth charts. | `/finance`, `/api/finance/*` |
| **[`swagger/`](./swagger/)** | Interactive OpenAPI 3.0 Swagger documentation console and JSON spec generator. | `/`, `/docs`, `/openapi.json` |
| **[`index/`](./index/)** | HTTP Basic Auth middleware, security checkers, and route protection decorators. | Application middleware |
| **[`config/`](./config/)** | Environment configuration files, database files (`todo.db`, `invoices.db`), and secret schemas. | Application configuration |
| **[`css/`](./css/)** | Shared global design system (`shared.css`) with synchronized light/dark palette and navigation tokens. | Global stylesheets |
| **[`static/`](./static/)** | Static brand assets (`flash.png`, `flash.gif`, favicon). | Web assets |
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

Accessible at `http://localhost:5000/todo`, the To-Do module provides category-based task organization with drag-and-drop sequencing and automated weekly archival.

* **Eisenhower Categories**: Dynamic, color-accented category cards with live task counters.
* **Drag-and-Drop Reordering**: Immediate DOM reordering with background persistence to SQLite sort indices.
* **Monday 2:00 AM PST Archival Scheduler**: A background daemon thread archives all completed tasks weekly, keeping active boards focused while preserving full historical records.
* **Archival Management**: One-click "Archive Completed", full category archival, and conflict-checked restoration.

### To-Do Endpoints
| Endpoint | Method | Description |
| :--- | :--- | :--- |
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
├── InvoiceGenerator/tests/
│   ├── test_invoices.py       # DB, CRUD, calculations, and vector PDF bytes
│   └── test_integration.py    # Flask route registration and OpenAPI verification
├── ToDo/tests/
│   └── test_todo.py           # Task/category CRUD, reordering, and Monday auto-archive
├── TutoringCalculator/tests/
│   └── test_tutoring_calc.py  # Hours parsing, calendar scraping, and safeguards
└── Monitoring/tests/
    └── test_monitoring.py     # Hardware telemetry collectors and diagnostics
```

### Run All Tests Across the Repository
```bash
# Discover and run all 36+ automated tests
.venv/bin/python -m unittest discover -s . -p "test_*.py"
```

### Run Tests for a Specific Module
```bash
# Invoice Generator
.venv/bin/python -m unittest discover -s InvoiceGenerator/tests -p "test_*.py"

# To-Do Board
.venv/bin/python -m unittest discover -s ToDo/tests -p "test_*.py"

# Tutoring Calculator
.venv/bin/python -m unittest discover -s TutoringCalculator/tests -p "test_*.py"

# Monitoring
.venv/bin/python -m unittest discover -s Monitoring/tests -p "test_*.py"
```

---

## 📚 Project Documentation

Explore the following modular documentation files for end-to-end setup and architecture details:

### 🛠️ Infrastructure & Web Deployment (`docs/setup/`)
* **[Server Hardware & Environment Setup](docs/setup/server.md)** — Host machine provisioning (Ubuntu 24.04 LTS, UFW firewall, Docker CE, Node.js, Python, storage mounts, systemd timers).
* **[Website & Nginx Projects Deployment](docs/setup/website.md)** — Nginx reverse proxy configurations, PM2 process management, Docker web containers, and Python WSGI socket deployment.
* **[Hostinger DNS & Certbot SSL Guide](docs/setup/dns-and-ssl.md)** — Hostinger DNS CNAME configuration, TP-Link Deco DDNS routing, router port forwarding, and automated Let's Encrypt SSL.
* **[Nginx Template Configuration](docs/setup/nginx.conf.template)** — Production-tested Nginx reverse-proxy template blocks (Unix socket, static + API, and local port).
* **[Setup Reference Specification](docs/setup/setup.conf)** — Master network configuration and subdomain routing definitions.

### 🖥️ System Telemetry & Monitoring (`docs/monitoring/`)
* **[Monitoring Architecture & Endpoints](docs/monitoring/architecture.md)** — Non-blocking telemetry collectors, multi-threaded socket probes, memory/CPU metrics, and REST API specification.
* **[Services Matrix & Probes](docs/monitoring/services-matrix.md)** — Detailed specification for the 11 monitored services, port mappings, and alert threshold triggers.
* **[Dashboard Operations Guide](docs/monitoring/dashboard-guide.md)** — Visual design guide, process table sort controls, refresh intervals, and diagnostic audit suite usage.

### 🎓 Tutoring Invoicing Pipeline (`docs/tutoring-calc/`)
* **[Billing Workflow & Endpoints](docs/tutoring-calc/billing-workflow.md)** — Weekly billing cycle, calendar scraping mechanics, rate lookups, and spreadsheet updates.
* **[Approval Safeguards & SMS Text Dispatch](docs/tutoring-calc/approval-safeguard.md)** — Human-in-the-loop review, `CALCULATED` title safety gate, Twilio SMS text dispatch, and audit logging.
* **[Automation & Google OAuth 2.0 Setup](docs/tutoring-calc/automation-and-oauth.md)** — Crontab automation schedules, script workflows, and Google OAuth 2.0 token management.

---

## 🔗 Internal Module References

Each package maintains its own internal technical README:
* **[Invoice Generator Documentation](InvoiceGenerator/README.md)** — Vector PDF Platypus architecture, database schema, presets, and route reference.
* **[Finance Module Documentation](Finance/README.md)** — SimpleFIN Bridge integration, SQLite history engine, Net Worth tracking, and interactive growth charts.
* **[To-Do Module Documentation](ToDo/README.md)** — Category schema, Eisenhower sorting, drag-and-drop indexing, and the Monday 2 AM auto-archive daemon.
* **[Tutoring Calculator Documentation](TutoringCalculator/README.md)** — Google Drive/Sheets integration, calendar hour parsing, Twilio SMS safeguards, and CLI scripts.
* **[Monitoring Module Documentation](Monitoring/README.md)** — Telemetry package, collector functions, process table sort controls, and UI templates.
* **[Swagger & OpenAPI Documentation](swagger/README.md)** — OpenAPI 3.0 specification generator, Swagger UI console, and schema definitions.
* **[Index & Security Documentation](index/README.md)** — HTTP Basic Authentication middleware, secret credentials resolution, and path whitelist rules.

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
4. **`TutoringCalculator/keys/token.pickle`** *(Ignored by Git)*:
   * Serialized Google OAuth 2.0 offline access token and auto-refresh token.
5. **`config/todo.db` & `config/invoices.db`** *(Ignored by Git)*:
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
