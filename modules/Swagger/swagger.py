import json
import os
from flask import Blueprint, jsonify, render_template_string, send_from_directory

swagger_bp = Blueprint('swagger', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, 'config')


def load_app_host():
    for folder in [CONFIG_DIR, BASE_DIR]:
        config_path = os.path.join(folder, 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f).get('APP_HOST')
            except Exception:
                pass
    return None


app_host = load_app_host()
servers = [{"url": "/", "description": "Current Server Host"}]
if app_host:
    servers.append({"url": app_host, "description": "Dev Production Server"})
servers.append({"url": "http://localhost:5000", "description": "Local Development Server"})

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Flash Server API",
        "description": "Interactive API Documentation and Test Execution Console for Stephen Giang's Flash Server Backend.",
        "version": "1.0.0"
    },
    "servers": servers,
    "tags": [
        {
            "name": "Tutoring Calculator",
            "description": "Crossroads Tutoring weekly billing, calendar event parsing, sheet management, Twilio reminders, and OAuth."
        },
        {
            "name": "Monitoring",
            "description": "Flash Server hardware telemetry, disk storage monitoring, service health matrix, and diagnostic test suite."
        },
        {
            "name": "To Do",
            "description": "Interactive Crossroads To-Do board, categorized task items, manual archiving, and reordering API."
        },
        {
            "name": "Invoices",
            "description": "Pure-Python on-demand vector PDF invoice generation, multi-company profiles, clients, presets, and history."
        },
        {
            "name": "Finance",
            "description": "SimpleFIN Bridge integration, live account balances, SQLite history keeping, net worth tracking, and interactive growth charts."
        }
    ],
    "components": {
        "securitySchemes": {
            "basicAuth": {
                "type": "http",
                "scheme": "basic",
                "description": "HTTP Basic Authentication using USERNAME and PASSWORD"
            }
        }
    },
    "security": [
        {"basicAuth": []}
    ],
    "paths": {
        "/test": {
            "get": {
                "tags": ["Tutoring Calculator"],
                "summary": "Health Check / Ping",
                "description": "Simple test endpoint to verify server status.",
                "responses": {
                    "200": {
                        "description": "Server is up and running."
                    }
                }
            }
        },
        "/api/tutoring/status": {
            "get": {
                "tags": ["Tutoring Calculator"],
                "summary": "Get Tutoring Service & Sheet Status",
                "description": "Returns live billing dates, Google auth state, current week sheet metadata, and Drive folder links.",
                "parameters": [
                    {
                        "name": "check_sheet",
                        "in": "query",
                        "required": False,
                        "description": "Pass 1 to search Google Drive for the current week's sheet.",
                        "schema": {"type": "integer", "enum": [0, 1], "default": 0}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Tutoring calculation and cloud service status."
                    }
                }
            }
        },
        "/api/tutoring/dates": {
            "get": {
                "tags": ["Tutoring Calculator"],
                "summary": "Get Billing Date Range",
                "description": "Calculates the previous Monday date (or previous Monday if today is Monday) and the following Sunday in MM.DD.YY format.",
                "responses": {
                    "200": {
                        "description": "Calculated start_date and end_date.",
                        "content": {
                            "application/json": {
                                "example": {
                                    "start_date": "08.31.26",
                                    "end_date": "09.06.26",
                                    "start_date_full": "2026-08-31",
                                    "end_date_full": "2026-09-06"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/tutoring/copy-template": {
            "post": {
                "tags": ["Tutoring Calculator"],
                "summary": "Copy Student Pay Template Sheet",
                "description": "Copies the master template sheet into the year folder, renames it to 'MM.DD.YY - MM.DD.YY CALCULATED', updates C1 (start date) and D1 (end date), and returns the sheet ID and editable URL.",
                "parameters": [
                    {
                        "name": "start_date",
                        "in": "query",
                        "required": False,
                        "description": "Start date in MM.DD.YY or YYYY-MM-DD format. If omitted, automatically computed.",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "end_date",
                        "in": "query",
                        "required": False,
                        "description": "End date in MM.DD.YY or YYYY-MM-DD format. If omitted, automatically computed.",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Template copied successfully.",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "sheet_id": "1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA",
                                    "sheet_url": "https://docs.google.com/spreadsheets/d/1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA/edit",
                                    "title": "08.31.26 - 09.06.26 CALCULATED"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/tutoring/calc-hours": {
            "get": {
                "tags": ["Tutoring Calculator"],
                "summary": "Calculate Tutoring Hours from Google Calendar",
                "description": "Queries the 'Tutoring' calendar for events ending in 'Tutoring' with default/primary color, consolidating hours by student's first name.",
                "parameters": [
                    {
                        "name": "start_date",
                        "in": "query",
                        "required": True,
                        "description": "Start date in MM.DD.YY or YYYY-MM-DD format",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "end_date",
                        "in": "query",
                        "required": True,
                        "description": "End date in MM.DD.YY or YYYY-MM-DD format",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Tutoring hours consolidated by student name.",
                        "content": {
                            "application/json": {
                                "example": {
                                    "Elijah": 3.0,
                                    "Ellie": 4.5,
                                    "Amelie": 4.0,
                                    "Michael": 5.75,
                                    "Jack": 3.0
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/tutoring/previous-balances": {
            "get": {
                "tags": ["Tutoring Calculator"],
                "summary": "Fetch Prior Week's Unpaid Balances",
                "description": "Finds the sheet for the previous week (7 days prior to start_date) and returns all students whose status is 'Need to Pay' along with their Total Balance.",
                "parameters": [
                    {
                        "name": "start_date",
                        "in": "query",
                        "required": True,
                        "description": "Start date of current week (MM.DD.YY)",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "end_date",
                        "in": "query",
                        "required": False,
                        "description": "End date of current week (MM.DD.YY)",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Previous balances by student first name.",
                        "content": {
                            "application/json": {
                                "example": {
                                    "Elijah": 180.0,
                                    "Ellie": 270.0
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/tutoring/update-sheet": {
            "post": {
                "tags": ["Tutoring Calculator"],
                "summary": "Update Sheet Hours or Pay Statuses",
                "description": "Action 'update_hours': reads C1/D1 dates, fetches calc-hours and previous-balances, and updates Column D (# Hours) and Column G (Remaining Balance). Action 'update_pay_status': converts blank statuses for active students to 'Need to Pay'.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["sheet_id", "action"],
                                "properties": {
                                    "sheet_id": {"type": "string", "description": "Google Sheet ID to update"},
                                    "action": {
                                        "type": "string",
                                        "enum": ["update_hours", "update_pay_status"],
                                        "description": "Action to perform"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Sheet updated successfully.",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "sheet_id": "1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA",
                                    "sheet_url": "https://docs.google.com/spreadsheets/d/1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA/edit",
                                    "action": "update_hours"
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/tutoring/run-calc": {
            "post": {
                "tags": ["Tutoring Calculator"],
                "summary": "Run Weekly Pay Calculation (Full Orchestration)",
                "description": "Executes full weekly pay run (scheduled Mondays at 4:00 AM PST, or callable via /run-calc or /tutoring/run-calc): copies master template into year folder named 'MM.DD.YY - MM.DD.YY CALCULATED', extracts Google Calendar hours, retrieves prior unpaid balances, populates spreadsheet, and sends email summary (unless send_email=false).",
                "parameters": [
                    {
                        "name": "start_date",
                        "in": "query",
                        "required": False,
                        "description": "Billing start date (MM.DD.YY). Automatically computed if omitted.",
                        "schema": {"type": "string", "example": "09.14.26"}
                    },
                    {
                        "name": "end_date",
                        "in": "query",
                        "required": False,
                        "description": "Billing end date (MM.DD.YY). Automatically computed if omitted.",
                        "schema": {"type": "string", "example": "09.20.26"}
                    },
                    {
                        "name": "send_email",
                        "in": "query",
                        "required": False,
                        "description": "Whether to send notification email. Defaults to true (automatic for cron jobs). Set to false to omit email (used by dashboard button).",
                        "schema": {"type": "boolean", "default": True}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Weekly pay calculation completed successfully.",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "message": "Successfully calculated tutoring billing for 09.14.26 - 09.20.26. Email notification sent.",
                                    "sheet_id": "1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA",
                                    "sheet_url": "https://docs.google.com/spreadsheets/d/1S5f5pKJZAvEW49sOrv-mbA7bqZs9_93WbcUNCNMHJBA/edit",
                                    "sheet_title": "09.14.26 - 09.20.26 CALCULATED",
                                    "total_balance": "$480.00",
                                    "send_email": True,
                                    "email_status": "sent"
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "Calculation or Google API error."
                    }
                }
            }
        },
        "/api/tutoring/run-send-texts": {
            "post": {
                "tags": ["Tutoring Calculator"],
                "summary": "Run SMS Payment Reminders Guarded by Approval",
                "description": "Dispatches Twilio SMS reminders to parents (scheduled Mondays at 12:00 PM PST, or callable via /run-send-texts, /tutoring/run-send-texts, or /send-texts). Aborts if sheet title still contains 'CALCULATED'. If approved, sends SMS reminders to students with Total Balance > 0 and blank status, updates status to 'Need to Pay', and logs to text_messages.log.",
                "parameters": [
                    {
                        "name": "sheet_id",
                        "in": "query",
                        "required": False,
                        "description": "Google Sheet ID (optional; auto-locates current week's sheet if omitted)",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "SMS dispatch completed or skipped due to CALCULATED guard.",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "sent_count": 5,
                                    "messages": [
                                        {"student": "Elijah Dinh", "phone": "+19512190584", "status": "sent"}
                                    ]
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Multiple sheets found or invalid request."
                    }
                }
            }
        },
        "/api/tutoring/send-texts": {
            "post": {
                "tags": ["Tutoring Calculator"],
                "summary": "Send SMS Payment Reminders via Twilio",
                "description": "Checks sheet title for 'CALCULATED' (aborts if present). If approved, sends SMS reminders to parents for students with Total Balance > 0 and blank status, updates status to 'Need to Pay', logs to text_messages.log.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["sheet_id"],
                                "properties": {
                                    "sheet_id": {"type": "string", "description": "Google Sheet ID"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "SMS processing complete.",
                        "content": {
                            "application/json": {
                                "example": {
                                    "status": "success",
                                    "sent_count": 5,
                                    "messages": [
                                        {"student": "Elijah Dinh", "phone": "+19512190584", "status": "sent"}
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/tutoring/text-logs": {
            "get": {
                "tags": ["Tutoring Calculator"],
                "summary": "Retrieve Text Message Audit Logs",
                "description": "Returns the contents of text_messages.log containing full history of sent SMS payment notices.",
                "responses": {
                    "200": {
                        "description": "Log file content.",
                        "content": {
                            "text/plain": {
                                "example": "[2026-09-07 10:00:01 PST] SENT to Ms. Sandy (+19512190584) for Elijah Dinh: Elijah: $180.00..."
                            }
                        }
                    }
                }
            }
        },
        "/login_oauth": {
            "get": {
                "tags": ["Tutoring Calculator"],
                "summary": "Google OAuth 2.0 Login / Callback",
                "description": "Initiates Google OAuth 2.0 authorization or handles the redirect callback to acquire offline credentials with auto-refresh.",
                "responses": {
                    "302": {
                        "description": "Redirects to Google consent screen or returns to docs after login."
                    }
                }
            }
        },
        "/monitoring": {
            "get": {
                "tags": ["Monitoring"],
                "summary": "System Health & Telemetry Web Dashboard",
                "description": "Renders the interactive dashboard UI displaying hardware telemetry, storage shares, top processes, and service status.",
                "responses": {
                    "200": {
                        "description": "HTML Dashboard rendered."
                    }
                }
            }
        },
        "/api/monitoring/system": {
            "get": {
                "tags": ["Monitoring"],
                "summary": "System & Hardware Telemetry",
                "description": "Returns CPU load %, core count, load averages, temperature, RAM/Swap metrics, and host/kernel specs.",
                "responses": {
                    "200": {
                        "description": "JSON hardware and host specifications."
                    }
                }
            }
        },
        "/api/monitoring/processes": {
            "get": {
                "tags": ["Monitoring"],
                "summary": "Top Processes by RAM or CPU",
                "description": "Returns list of top running processes sorted by RAM (RSS) or CPU utilization.",
                "parameters": [
                    {
                        "name": "sort",
                        "in": "query",
                        "required": False,
                        "description": "Sort metric: 'ram' (default) or 'cpu'.",
                        "schema": {"type": "string", "enum": ["ram", "cpu"], "default": "ram"}
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "description": "Number of processes to return (default 10).",
                        "schema": {"type": "integer", "default": 10}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "JSON list of top processes."
                    }
                }
            }
        },
        "/api/monitoring/storage": {
            "get": {
                "tags": ["Monitoring"],
                "summary": "Storage Devices & Mounts",
                "description": "Returns capacity, usage, and alert status for all mounted disks and flash-server network shares.",
                "responses": {
                    "200": {
                        "description": "JSON array of storage partitions."
                    }
                }
            }
        },
        "/api/monitoring/services": {
            "get": {
                "tags": ["Monitoring"],
                "summary": "Services & Docker Health Matrix",
                "description": "Probes all configured flash-server services (Immich, Jellyfin, qBittorrent, n8n, Postgres, AIU, etc.) and returns real-time status and latencies.",
                "responses": {
                    "200": {
                        "description": "JSON array of service statuses."
                    }
                }
            }
        },
        "/api/monitoring/diagnostics": {
            "get": {
                "tags": ["Monitoring"],
                "summary": "Diagnostic Test Suite Audit",
                "description": "Runs comprehensive health checks across disks, RAM, thermals, services, and cron jobs, returning an overall audit result.",
                "responses": {
                    "200": {
                        "description": "JSON diagnostic audit report."
                    }
                }
            }
        },
        "/api/todo/categories": {
            "get": {
                "tags": ["To Do"],
                "summary": "List Categories",
                "description": "Retrieves the list of active task categories and associated hex color codes and status from the SQLite categories table.",
                "responses": {
                    "200": {
                        "description": "JSON list of categories."
                    }
                }
            },
            "post": {
                "tags": ["To Do"],
                "summary": "Create New Category",
                "description": "Creates a new category with a unique name and color.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string", "example": "New Project"},
                                    "color": {"type": "string", "example": "#5b95cb"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "JSON object with success boolean and created category."
                    },
                    "400": {
                        "description": "Category name required or duplicate active category."
                    },
                    "409": {
                        "description": "Category exists in archived status (conflict)."
                    }
                }
            }
        },
        "/api/todo/categories/{category_id}/archive": {
            "post": {
                "tags": ["To Do"],
                "summary": "Archive Category",
                "description": "Archives a category and cascades to automatically archive all its active tasks.",
                "parameters": [
                    {
                        "name": "category_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "JSON object with category and tasks_archived count."
                    },
                    "404": {
                        "description": "Category not found."
                    }
                }
            }
        },
        "/api/todo/categories/{category_id}/restore": {
            "post": {
                "tags": ["To Do"],
                "summary": "Restore Category",
                "description": "Restores an archived category to active status without changing task archival status.",
                "parameters": [
                    {
                        "name": "category_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "JSON object with restored active category."
                    },
                    "404": {
                        "description": "Category not found."
                    }
                }
            }
        },
        "/api/todo/categories/archived-summary": {
            "get": {
                "tags": ["To Do"],
                "summary": "List Archived Categories with Tasks",
                "description": "Retrieves all archived categories and their archived tasks.",
                "responses": {
                    "200": {
                        "description": "JSON object with archived_categories list."
                    }
                }
            }
        },
        "/api/todo/categories/status": {
            "patch": {
                "tags": ["To Do"],
                "summary": "Update Category Status",
                "description": "Updates the status text bar for a specific category.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["category"],
                                "properties": {
                                    "category": {"type": "string", "example": "ASH"},
                                    "status": {"type": "string", "example": "In Progress"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "JSON object with success boolean and updated category."
                    },
                    "400": {
                        "description": "Category name required."
                    }
                }
            }
        },
        "/api/todo/items": {
            "get": {
                "tags": ["To Do"],
                "summary": "List Tasks",
                "description": "Retrieves active or archived tasks, optionally filtered by category name.",
                "parameters": [
                    {
                        "name": "status",
                        "in": "query",
                        "required": False,
                        "description": "Task status filter ('active' or 'archived', defaults to 'active')",
                        "schema": {"type": "string", "enum": ["active", "archived"], "default": "active"}
                    },
                    {
                        "name": "category",
                        "in": "query",
                        "required": False,
                        "description": "Optional category name filter",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "JSON object with status, categories, and tasks list."
                    }
                }
            },
            "post": {
                "tags": ["To Do"],
                "summary": "Create New Task",
                "description": "Adds a new task item under a specified category box.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["text"],
                                "properties": {
                                    "text": {"type": "string", "example": "Grade homework assignments"},
                                    "category": {"type": "string", "example": "Crossroads Tutoring"},
                                    "day_tag": {"type": "string", "example": "Monday"},
                                    "size_tag": {"type": "string", "enum": ["Small", "Medium", "Long"], "example": "Medium"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Task created successfully."
                    },
                    "400": {
                        "description": "Validation error."
                    }
                }
            }
        },
        "/api/todo/items/{item_id}": {
            "patch": {
                "tags": ["To Do"],
                "summary": "Update Task",
                "description": "Modifies task text, completion status, category, weekday tag, or size tag.",
                "parameters": [
                    {
                        "name": "item_id",
                        "in": "path",
                        "required": True,
                        "description": "Task ID",
                        "schema": {"type": "integer"}
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "completed": {"type": "integer", "enum": [0, 1]},
                                    "category": {"type": "string"},
                                    "day_tag": {"type": "string", "example": "Monday"},
                                    "size_tag": {"type": "string", "enum": ["Small", "Medium", "Long", ""], "example": "Small"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Task updated successfully."
                    },
                    "404": {
                        "description": "Task not found."
                    }
                }
            },
            "delete": {
                "tags": ["To Do"],
                "summary": "Delete Task",
                "description": "Permanently deletes a task from the database.",
                "parameters": [
                    {
                        "name": "item_id",
                        "in": "path",
                        "required": True,
                        "description": "Task ID",
                        "schema": {"type": "integer"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Task deleted successfully."
                    },
                    "404": {
                        "description": "Task not found."
                    }
                }
            }
        },
        "/api/todo/items/{item_id}/restore": {
            "post": {
                "tags": ["To Do"],
                "summary": "Restore Archived Task",
                "description": "Restores an archived task back to the active board.",
                "parameters": [
                    {
                        "name": "item_id",
                        "in": "path",
                        "required": True,
                        "description": "Task ID",
                        "schema": {"type": "integer"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Task restored."
                    },
                    "404": {
                        "description": "Task not found."
                    }
                }
            }
        },
        "/api/todo/reorder": {
            "post": {
                "tags": ["To Do"],
                "summary": "Reorder Tasks",
                "description": "Updates display order and category assignments for ordered tasks.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["items"],
                                "properties": {
                                    "items": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["id", "display_order"],
                                            "properties": {
                                                "id": {"type": "integer"},
                                                "display_order": {"type": "integer"},
                                                "category": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Tasks reordered successfully."
                    }
                }
            }
        },
        "/api/todo/archive-completed": {
            "post": {
                "tags": ["To Do"],
                "summary": "Archive Completed Tasks",
                "description": "Immediately archives all currently crossed-out (completed) active tasks across categories.",
                "responses": {
                    "200": {
                        "description": "Archived count returned."
                    }
                }
            }
        },
        "/api/todo/archive-all": {
            "post": {
                "tags": ["To Do"],
                "summary": "Archive All Tasks",
                "description": "Archives all active tasks (optionally filtered by category).",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "category": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Archived count returned."
                    }
                }
            }
        },
        "/api/todo/delete-all": {
            "post": {
                "tags": ["To Do"],
                "summary": "Delete All Tasks",
                "description": "Permanently deletes all tasks in a view (active or archived, optionally filtered by category).",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string", "enum": ["active", "archived"]},
                                    "category": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Deleted count returned."
                    }
                }
            }
        },
        "/invoices": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Invoices Management Console",
                "description": "Interactive web UI for invoice history, builder, and company/client management.",
                "responses": {
                    "200": {"description": "HTML page rendered."}
                }
            }
        },
        "/invoices/{invoice_id}/preview": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Print Preview Invoice",
                "description": "Clean, print-ready HTML invoice view rendered on-demand from database data.",
                "parameters": [
                    {"name": "invoice_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Print-ready HTML layout."},
                    "404": {"description": "Invoice not found."}
                }
            }
        },
        "/api/invoices/summary": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Dashboard Aggregate Metrics",
                "description": "Returns total invoiced, outstanding balances, collected payments, and client counts.",
                "responses": {
                    "200": {"description": "Summary metrics JSON."}
                }
            }
        },
        "/api/invoices/next-number": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Get Next Invoice Number",
                "description": "Calculates the next sequential invoice number for current year (e.g. INV-YYYY-001).",
                "responses": {
                    "200": {"description": "Next invoice number string."}
                }
            }
        },
        "/api/invoices/senders": {
            "get": {
                "tags": ["Invoices"],
                "summary": "List Sender Profiles",
                "description": "Returns all business/company profiles used in the 'From' block.",
                "responses": {
                    "200": {"description": "List of sender profiles."}
                }
            },
            "post": {
                "tags": ["Invoices"],
                "summary": "Create Sender Profile",
                "description": "Creates a new business or entity profile.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                    "phone": {"type": "string"},
                                    "address": {"type": "string"},
                                    "website": {"type": "string"},
                                    "payment_instructions": {"type": "string"},
                                    "default_notes": {"type": "string"},
                                    "is_default": {"type": "integer", "enum": [0, 1]}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {"description": "Sender profile created."}
                }
            }
        },
        "/api/invoices/senders/{sender_id}": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Get Sender Profile",
                "parameters": [
                    {"name": "sender_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Sender profile object."},
                    "404": {"description": "Sender profile not found."}
                }
            },
            "put": {
                "tags": ["Invoices"],
                "summary": "Update Sender Profile",
                "parameters": [
                    {"name": "sender_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                    "phone": {"type": "string"},
                                    "address": {"type": "string"},
                                    "website": {"type": "string"},
                                    "payment_instructions": {"type": "string"},
                                    "default_notes": {"type": "string"},
                                    "is_default": {"type": "integer", "enum": [0, 1]}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Updated successfully."}
                }
            },
            "delete": {
                "tags": ["Invoices"],
                "summary": "Delete Sender Profile",
                "parameters": [
                    {"name": "sender_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Deleted successfully."}
                }
            }
        },
        "/api/invoices/clients": {
            "get": {
                "tags": ["Invoices"],
                "summary": "List Saved Clients",
                "description": "Returns all saved client records.",
                "responses": {
                    "200": {"description": "List of clients."}
                }
            },
            "post": {
                "tags": ["Invoices"],
                "summary": "Create Client",
                "description": "Adds a new client record.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                    "phone": {"type": "string"},
                                    "address": {"type": "string"},
                                    "notes": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {"description": "Client created."}
                }
            }
        },
        "/api/invoices/clients/{client_id}": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Get Client",
                "parameters": [
                    {"name": "client_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Client object."},
                    "404": {"description": "Client not found."}
                }
            },
            "put": {
                "tags": ["Invoices"],
                "summary": "Update Client",
                "parameters": [
                    {"name": "client_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                    "phone": {"type": "string"},
                                    "address": {"type": "string"},
                                    "notes": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Updated successfully."}
                }
            },
            "delete": {
                "tags": ["Invoices"],
                "summary": "Delete Client",
                "parameters": [
                    {"name": "client_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Deleted successfully."}
                }
            }
        },
        "/api/invoices/presets/{client_id}": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Get Client Presets",
                "description": "Returns saved recurring line item presets for a client.",
                "parameters": [
                    {"name": "client_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "List of presets."}
                }
            }
        },
        "/api/invoices/presets": {
            "get": {
                "tags": ["Invoices"],
                "summary": "List All Presets",
                "description": "Lists presets across all clients.",
                "responses": {
                    "200": {"description": "List of presets."}
                }
            },
            "post": {
                "tags": ["Invoices"],
                "summary": "Create Client Preset",
                "description": "Saves reusable line items and optional recurring schedule as a template for a client.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["client_id", "preset_name"],
                                "properties": {
                                    "client_id": {"type": "integer"},
                                    "preset_name": {"type": "string"},
                                    "default_due_days": {"type": "integer"},
                                    "items": {"type": "array", "items": {"type": "object"}},
                                    "notes": {"type": "string"},
                                    "discount_amount": {"type": "number"},
                                    "tax_rate": {"type": "number"},
                                    "payment_instructions": {"type": "string"},
                                    "is_recurring": {"type": "boolean"},
                                    "recurrence_type": {"type": "string", "enum": ["monthly", "biweekly", "weekly"]},
                                    "recurrence_day": {"type": "integer"},
                                    "recurrence_start_date": {"type": "string"},
                                    "sender_id": {"type": "integer"},
                                    "auto_status": {"type": "string", "enum": ["draft", "sent"]}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {"description": "Preset created."}
                }
            }
        },
        "/api/invoices/recurring": {
            "get": {
                "tags": ["Invoices"],
                "summary": "List Recurring Presets",
                "description": "Lists all active recurring invoice templates and rules across clients.",
                "responses": {
                    "200": {"description": "List of active recurring templates."}
                }
            }
        },
        "/api/invoices/recurring/run": {
            "post": {
                "tags": ["Invoices"],
                "summary": "Trigger Daily Recurring Invoices Check",
                "description": "Evaluates recurring preset schedules for a given date (defaults to today in PST) and generates invoices.",
                "parameters": [
                    {"name": "date", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Target date (YYYY-MM-DD) to evaluate against."}
                ],
                "responses": {
                    "200": {"description": "Recurring run summary and list of created invoices."}
                }
            }
        },
        "/api/invoices": {
            "get": {
                "tags": ["Invoices"],
                "summary": "List Invoices",
                "description": "Lists invoices with optional filtering by status, search, client, sender, and dates.",
                "parameters": [
                    {"name": "status", "in": "query", "schema": {"type": "string"}},
                    {"name": "search", "in": "query", "schema": {"type": "string"}},
                    {"name": "client_id", "in": "query", "schema": {"type": "integer"}},
                    {"name": "sender_id", "in": "query", "schema": {"type": "integer"}},
                    {"name": "start_date", "in": "query", "schema": {"type": "string"}},
                    {"name": "end_date", "in": "query", "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {"description": "List of invoices."}
                }
            },
            "post": {
                "tags": ["Invoices"],
                "summary": "Create Invoice",
                "description": "Creates an invoice, saves snapshots and line items.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["client_name", "items"],
                                "properties": {
                                    "invoice_number": {"type": "string"},
                                    "sender_id": {"type": "integer"},
                                    "client_id": {"type": "integer"},
                                    "client_name": {"type": "string"},
                                    "issue_date": {"type": "string"},
                                    "due_date": {"type": "string"},
                                    "status": {"type": "string", "enum": ["draft", "sent", "paid", "void"]},
                                    "discount_amount": {"type": "number"},
                                    "tax_rate": {"type": "number"},
                                    "payment_instructions": {"type": "string"},
                                    "notes": {"type": "string"},
                                    "items": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["description"],
                                            "properties": {
                                                "description": {"type": "string"},
                                                "quantity": {"type": "number"},
                                                "unit_price": {"type": "number"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "201": {"description": "Invoice created."}
                }
            }
        },
        "/api/invoices/{invoice_id}": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Get Invoice Detail",
                "description": "Returns invoice details including historical snapshots and line items.",
                "parameters": [
                    {"name": "invoice_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Invoice details object."},
                    "404": {"description": "Invoice not found."}
                }
            },
            "put": {
                "tags": ["Invoices"],
                "summary": "Update Invoice",
                "parameters": [
                    {"name": "invoice_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Invoice updated."}
                }
            },
            "delete": {
                "tags": ["Invoices"],
                "summary": "Delete Invoice",
                "parameters": [
                    {"name": "invoice_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Invoice deleted."}
                }
            }
        },
        "/api/invoices/{invoice_id}/status": {
            "patch": {
                "tags": ["Invoices"],
                "summary": "Update Invoice Status",
                "description": "Updates invoice status (draft, sent, paid, overdue, void).",
                "parameters": [
                    {"name": "invoice_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["status"],
                                "properties": {
                                    "status": {"type": "string", "enum": ["draft", "sent", "paid", "overdue", "void"]}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Status updated."}
                }
            }
        },
        "/api/invoices/{invoice_id}/duplicate": {
            "post": {
                "tags": ["Invoices"],
                "summary": "Duplicate Invoice",
                "description": "Duplicates an invoice into a fresh draft with today's date and next invoice #.",
                "parameters": [
                    {"name": "invoice_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "201": {"description": "Duplicated draft created."}
                }
            }
        },
        "/api/invoices/{invoice_id}/pdf": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Download Pure-Python Vector PDF",
                "description": "Generates a vector PDF on-the-fly from stored invoice data and streams as download. Zero disk PDF storage.",
                "parameters": [
                    {"name": "invoice_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {
                        "description": "Vector PDF binary stream.",
                        "content": {"application/pdf": {}}
                    }
                }
            }
        },
        "/api/finance/summary": {
            "get": {
                "tags": ["Finance"],
                "summary": "Financial KPI Summary",
                "description": "Returns calculated Net Worth, Total Assets, Total Liabilities, Liquid Cash, Investments, Debts, and categorized accounts.",
                "responses": {
                    "200": {"description": "Financial summary data."}
                }
            }
        },
        "/api/finance/accounts": {
            "get": {
                "tags": ["Finance"],
                "summary": "List All Financial Accounts",
                "description": "Returns all 10 institutions and accounts with current balances, rates, and rewards metadata.",
                "responses": {
                    "200": {"description": "List of accounts."}
                }
            }
        },
        "/api/finance/history": {
            "get": {
                "tags": ["Finance"],
                "summary": "Historical Growth Trajectory",
                "description": "Returns time-series snapshots for the interactive growth chart. Query param timeframe: 1m, 3m, 6m, 1y, all.",
                "parameters": [
                    {"name": "timeframe", "in": "query", "required": False, "schema": {"type": "string", "enum": ["1m", "3m", "6m", "1y", "all"]}}
                ],
                "responses": {
                    "200": {"description": "Historical snapshot data formatted for Chart.js."}
                }
            }
        },
        "/api/finance/sync": {
            "post": {
                "tags": ["Finance"],
                "summary": "Sync Accounts from SimpleFIN",
                "description": "Fetches latest balances from SimpleFIN Bridge and stores a new historical snapshot in SQLite.",
                "responses": {
                    "200": {"description": "Sync status and count of updated accounts."}
                }
            }
        },
        "/api/finance/claim": {
            "post": {
                "tags": ["Finance"],
                "summary": "Claim SimpleFIN Token / Save Access URL",
                "description": "Exchanges a one-time SimpleFIN claim token for an access URL or saves an access URL directly.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "claim_token": {"type": "string"},
                                    "access_url": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Claim status."}
                }
            }
        },
        "/api/finance/settings": {
            "get": {
                "tags": ["Finance"],
                "summary": "SimpleFIN Connection Settings",
                "description": "Returns current connection status, masked access URL, and last sync timestamp.",
                "responses": {
                    "200": {"description": "Connection settings status."}
                }
            }
        },
        "/todo": {
            "get": {
                "tags": ["To Do"],
                "summary": "To-Do Board Page",
                "description": "Renders the interactive To-Do board (HTML).",
                "responses": {"200": {"description": "HTML page."}}
            }
        },
        "/api/todo/categories/{category_id}": {
            "patch": {
                "tags": ["To Do"],
                "summary": "Update Category",
                "description": "Updates a category's name, color, status or custom status text, or display order. Renaming a category moves its tasks with it. Also accepts PUT.",
                "parameters": [
                    {"name": "category_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "color": {"type": "string", "example": "#5b95cb"},
                                    "status": {"type": "string", "description": "'active' or 'archived'. Any other text is stored as the custom status text."},
                                    "custom_status": {"type": "string"},
                                    "display_order": {"type": "integer"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "JSON object with success boolean and updated category."},
                    "400": {"description": "Invalid name or color, or duplicate name."},
                    "404": {"description": "Category not found."}
                }
            }
        },
        "/api/todo/categories/{category_name}/status": {
            "patch": {
                "tags": ["To Do"],
                "summary": "Update Category Status (by Name in Path)",
                "description": "Updates the status text bar of the category named in the URL. Also accepts PUT and POST.",
                "parameters": [
                    {"name": "category_name", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"status": {"type": "string", "example": "In Progress"}}
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "JSON object with success boolean and updated category."}
                }
            }
        },
        "/api/invoices/presets/detail/{preset_id}": {
            "get": {
                "tags": ["Invoices"],
                "summary": "Get Preset",
                "description": "Returns a single preset by ID.",
                "parameters": [
                    {"name": "preset_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Preset object."},
                    "404": {"description": "Preset not found."}
                }
            }
        },
        "/api/invoices/presets/{preset_id}": {
            "put": {
                "tags": ["Invoices"],
                "summary": "Update Preset",
                "description": "Replaces a preset's name, line items, and recurrence settings.",
                "parameters": [
                    {"name": "preset_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["preset_name"],
                                "properties": {
                                    "preset_name": {"type": "string"},
                                    "default_due_days": {"type": "integer"},
                                    "items": {"type": "array", "items": {"type": "object"}},
                                    "notes": {"type": "string"},
                                    "discount_amount": {"type": "number"},
                                    "tax_rate": {"type": "number"},
                                    "payment_instructions": {"type": "string"},
                                    "is_recurring": {"type": "boolean"},
                                    "recurrence_type": {"type": "string", "enum": ["monthly", "biweekly", "weekly"]},
                                    "recurrence_day": {"type": "integer"},
                                    "recurrence_start_date": {"type": "string"},
                                    "sender_id": {"type": "integer"},
                                    "auto_status": {"type": "string", "enum": ["draft", "sent"]}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Preset updated."},
                    "400": {"description": "preset_name is required."},
                    "404": {"description": "Preset not found."}
                }
            },
            "delete": {
                "tags": ["Invoices"],
                "summary": "Delete Preset",
                "parameters": [
                    {"name": "preset_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Preset deleted."},
                    "404": {"description": "Preset not found."}
                }
            }
        },
        "/api/invoices/senders/{sender_id}/default": {
            "patch": {
                "tags": ["Invoices"],
                "summary": "Set Default Sender",
                "description": "Marks a sender profile as the default used for new and recurring invoices.",
                "parameters": [
                    {"name": "sender_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Default sender updated."},
                    "404": {"description": "Sender profile not found."}
                }
            }
        },
        "/finance": {
            "get": {
                "tags": ["Finance"],
                "summary": "Financial Dashboard Page",
                "description": "Renders the interactive Financial Dashboard (HTML).",
                "responses": {"200": {"description": "HTML page."}}
            }
        },
        "/api/finance/disconnect": {
            "post": {
                "tags": ["Finance"],
                "summary": "Disconnect SimpleFIN",
                "description": "Clears the stored SimpleFIN access URL and claim token.",
                "responses": {"200": {"description": "Credentials removed."}}
            }
        },
        "/api/finance/settings/order": {
            "get": {
                "tags": ["Finance"],
                "summary": "Get Account Display Order",
                "description": "Returns the saved custom account order for each category (cash, credit, investment, property_mortgage).",
                "responses": {"200": {"description": "Object with an `orders` map of category to list of account IDs."}}
            },
            "post": {
                "tags": ["Finance"],
                "summary": "Save Account Display Order",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["category", "order"],
                                "properties": {
                                    "category": {"type": "string", "example": "cash"},
                                    "order": {"type": "array", "items": {"type": "string"}}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Order saved."},
                    "400": {"description": "Invalid order payload."}
                }
            }
        },
        "/api/finance/account/add": {
            "post": {
                "tags": ["Finance"],
                "summary": "Add Manual Account",
                "description": "Creates a manual account the bridge cannot see (property, private note, crypto). `account_type` is normalized: cash/savings, checking, credit, investment/retirement, or property_mortgage (negative balance becomes a mortgage). Also served at /api/finance/accounts/add.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "institution": {"type": "string"},
                                    "account_type": {"type": "string", "example": "property_mortgage"},
                                    "balance": {"type": "number"},
                                    "account_number_mask": {"type": "string"},
                                    "currency": {"type": "string"},
                                    "apy_interest": {"type": "string"},
                                    "rewards_status": {"type": "string"},
                                    "credit_limit": {"type": "number"},
                                    "vested_balance": {"type": "number"},
                                    "holdings_summary": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Account created."},
                    "400": {"description": "Account name is required."}
                }
            }
        },
        "/api/finance/account/{account_id}": {
            "post": {
                "tags": ["Finance"],
                "summary": "Update Account",
                "description": "Updates account name, institution, type, balance, and metadata. Records a new snapshot.",
                "parameters": [
                    {"name": "account_id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "institution": {"type": "string"},
                                    "account_type": {"type": "string"},
                                    "account_number_mask": {"type": "string"},
                                    "balance": {"type": "number"},
                                    "apy_interest": {"type": "string"},
                                    "rewards_status": {"type": "string"},
                                    "holdings_summary": {"type": "string"},
                                    "credit_limit": {"type": "number"},
                                    "vested_balance": {"type": "number"},
                                    "simplefin_id": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Account updated."},
                    "404": {"description": "Account not found."}
                }
            },
            "delete": {
                "tags": ["Finance"],
                "summary": "Delete Account",
                "description": "Deletes an account and its history, then records a new snapshot. Also served as POST /api/finance/account/{account_id}/delete.",
                "parameters": [
                    {"name": "account_id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {"description": "Account deleted."},
                    "404": {"description": "Account not found."}
                }
            }
        },
        "/api/finance/account/{account_id}/delete": {
            "post": {
                "tags": ["Finance"],
                "summary": "Delete Account (POST form)",
                "description": "Same as DELETE /api/finance/account/{account_id}, for clients that cannot send DELETE.",
                "parameters": [
                    {"name": "account_id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {
                    "200": {"description": "Account deleted."},
                    "404": {"description": "Account not found."}
                }
            }
        },
        "/api/finance/deduplicate": {
            "post": {
                "tags": ["Finance"],
                "summary": "Merge Duplicate Accounts",
                "description": "Merges duplicate accounts and links SimpleFIN IDs.",
                "responses": {"200": {"description": "Deduplication summary including merged_count."}}
            }
        },
        "/api/finance/budget": {
            "get": {
                "tags": ["Finance"],
                "summary": "Budget Summary",
                "description": "Returns monthly income and expense totals, net monthly cash flow, and the lists of income and expense items.",
                "responses": {"200": {"description": "Budget summary."}}
            }
        },
        "/api/finance/budget/item": {
            "post": {
                "tags": ["Finance"],
                "summary": "Create or Update Budget Item",
                "description": "Creates a budget item, or updates it when `id` is supplied.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "id": {"type": "integer"},
                                    "category": {"type": "string", "enum": ["income", "expense"]},
                                    "name": {"type": "string"},
                                    "amount": {"type": "number", "description": "Monthly amount."},
                                    "frequency": {"type": "string", "example": "monthly"},
                                    "raw_amount": {"type": "number"},
                                    "tax_status": {"type": "string", "enum": ["pre-tax", "post-tax"]},
                                    "due_date": {"type": "string"},
                                    "portal_url": {"type": "string"},
                                    "notes": {"type": "string"},
                                    "details_json": {"type": "object"},
                                    "is_active": {"type": "integer", "enum": [0, 1]},
                                    "sort_order": {"type": "integer"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Saved; returns item_id."},
                    "400": {"description": "Name is required."}
                }
            }
        },
        "/api/finance/budget/item/{item_id}": {
            "get": {
                "tags": ["Finance"],
                "summary": "Get Budget Item",
                "parameters": [
                    {"name": "item_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Budget item with parsed `details`."},
                    "404": {"description": "Budget item not found."}
                }
            },
            "delete": {
                "tags": ["Finance"],
                "summary": "Delete Budget Item",
                "parameters": [
                    {"name": "item_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Budget item removed."},
                    "404": {"description": "Item not found."}
                }
            }
        },
        "/api/finance/budget/toggle/{item_id}": {
            "post": {
                "tags": ["Finance"],
                "summary": "Toggle Budget Item Active",
                "parameters": [
                    {"name": "item_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {
                    "200": {"description": "Active state flipped."},
                    "404": {"description": "Item not found."}
                }
            }
        },
        "/tutoring": {
            "get": {
                "tags": ["Tutoring Calculator"],
                "summary": "Tutoring Dashboard Page",
                "description": "Renders the tutoring billing dashboard (HTML). Also served at /tutoring/dashboard.",
                "responses": {"200": {"description": "HTML page."}}
            }
        },
        "/privacy": {
            "get": {
                "tags": ["Tutoring Calculator"],
                "summary": "Privacy Policy",
                "description": "Public privacy policy page (no authentication), required for Google OAuth verification. Also served at /TutoringCalculator/privacy.",
                "security": [],
                "responses": {"200": {"description": "HTML page."}}
            }
        }
    }
}


def _add_method_alias(path, method, copy_from):
    """Documents an extra HTTP method that Flask routes to the same handler."""
    item = OPENAPI_SPEC["paths"][path]
    op = dict(item[copy_from])
    op["description"] = (op.get("description", "") + f" (Equivalent to {copy_from.upper()}.)").strip()
    item[method] = op


# Methods that share a handler with an already documented method.
_add_method_alias("/api/todo/items/{item_id}", "put", "patch")
_add_method_alias("/api/todo/categories/{category_id}", "put", "patch")
_add_method_alias("/api/todo/categories/status", "put", "patch")
_add_method_alias("/api/todo/categories/status", "post", "patch")
_add_method_alias("/api/todo/categories/{category_name}/status", "put", "patch")
_add_method_alias("/api/todo/categories/{category_name}/status", "post", "patch")
_add_method_alias("/api/invoices/recurring/run", "get", "post")

SWAGGER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Flash Server API</title>
  <link rel="stylesheet" href="/static/shared.css" />
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
  <link rel="icon" type="image/png" href="/static/flash.png" />
  <link rel="shortcut icon" type="image/png" href="/static/flash.png" />
  <style>
    body {
      margin: 0;
      padding: 0;
      background: #fafafa;
    }
    .topbar {
      display: none !important;
    }
    .swagger-ui .info {
      position: relative !important;
      min-height: 185px !important;
      padding-right: 280px !important;
    }
    .swagger-ui .info .title {
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      color: #1a73e8;
    }
    #flash-header-banner {
      position: absolute !important;
      top: 0 !important;
      right: 0 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      border-radius: 12px !important;
      overflow: hidden !important;
      box-shadow: 0 4px 18px rgba(0, 0, 0, 0.14) !important;
      border: 2px solid #eaeaea !important;
      background: #ffffff !important;
      transition: transform 0.25s ease, box-shadow 0.25s ease !important;
    }
    #flash-header-banner:hover {
      transform: scale(1.03) !important;
      box-shadow: 0 8px 28px rgba(0, 0, 0, 0.22) !important;
    }
    #flash-header-banner img {
      height: 170px !important;
      width: auto !important;
      display: block !important;
      border-radius: 10px !important;
      object-fit: contain !important;
    }
    @media (max-width: 900px) {
      .swagger-ui .info {
        padding-right: 0 !important;
        min-height: auto !important;
      }
      #flash-header-banner {
        position: static !important;
        margin: 20px auto 10px auto !important;
        width: fit-content !important;
        max-width: 100% !important;
      }
      #flash-header-banner img {
        height: 130px !important;
        max-width: 100% !important;
      }
    }
    @media (max-width: 600px) {
      .swagger-ui .wrapper {
        padding: 0 12px !important;
      }
      .swagger-ui .info {
        margin: 14px 0 !important;
      }
      .swagger-ui .info .title {
        font-size: 22px !important;
      }
      #flash-header-banner img {
        height: 100px !important;
      }
      .nav-btn, .swagger-btn {
        padding: 6px 10px !important;
        font-size: 12px !important;
      }
      .swagger-ui table {
        display: block !important;
        overflow-x: auto !important;
        max-width: 100% !important;
      }
      .swagger-ui .opblock-summary-path {
        word-break: break-all !important;
      }
    }
    :root {
      --background: #ffffff;
      --card: #ffffff;
      --border: #e5e7eb;
      --foreground: #333333;
      --primary: #3b82f6;
    }
    .dark, [data-theme="dark"] {
      --background: #171717;
      --card: #262626;
      --border: #404040;
      --foreground: #ffffff;
      --primary: #3b82f6;
    }
    /* BASE BACKGROUND & TEXT */
    [data-theme="dark"] body, .dark body {
      background: #171717 !important;
      color: #ffffff !important;
    }
    [data-theme="dark"] .swagger-ui, .dark .swagger-ui {
      color: #ffffff !important;
      background: #171717 !important;
    }

    /* REMOVE ALL INVERT FILTERS */
    [data-theme="dark"] .swagger-ui,
    .dark .swagger-ui,
    [data-theme="dark"] .swagger-ui *:not(.theme-icon),
    .dark .swagger-ui *:not(.theme-icon) {
      filter: none !important;
    }

    /* HEADER & BANNER */
    [data-theme="dark"] #flash-header-banner, .dark #flash-header-banner {
      background: #262626 !important;
      border: 1px solid #404040 !important;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4) !important;
    }

    /* EXHAUSTIVE ZERO GREY TEXT ENFORCEMENT IN DARK MODE */
    [data-theme="dark"] .swagger-ui p,
    .dark .swagger-ui p,
    [data-theme="dark"] .swagger-ui span:not(.opblock-summary-method):not(.required),
    .dark .swagger-ui span:not(.opblock-summary-method):not(.required),
    [data-theme="dark"] .swagger-ui div:not(.opblock-summary-method),
    .dark .swagger-ui div:not(.opblock-summary-method),
    [data-theme="dark"] .swagger-ui label,
    .dark .swagger-ui label,
    [data-theme="dark"] .swagger-ui td,
    .dark .swagger-ui td,
    [data-theme="dark"] .swagger-ui th,
    .dark .swagger-ui th,
    [data-theme="dark"] .swagger-ui small,
    .dark .swagger-ui small,
    [data-theme="dark"] .swagger-ui i,
    .dark .swagger-ui i,
    [data-theme="dark"] .swagger-ui em,
    .dark .swagger-ui em,
    [data-theme="dark"] .swagger-ui strong,
    .dark .swagger-ui strong,
    [data-theme="dark"] .swagger-ui b,
    .dark .swagger-ui b,
    [data-theme="dark"] .swagger-ui h1, .dark .swagger-ui h1,
    [data-theme="dark"] .swagger-ui h2, .dark .swagger-ui h2,
    [data-theme="dark"] .swagger-ui h3, .dark .swagger-ui h3,
    [data-theme="dark"] .swagger-ui h4, .dark .swagger-ui h4,
    [data-theme="dark"] .swagger-ui h5, .dark .swagger-ui h5,
    [data-theme="dark"] .swagger-ui .opblock-description-wrapper,
    .dark .swagger-ui .opblock-description-wrapper,
    [data-theme="dark"] .swagger-ui .opblock-description-wrapper p,
    .dark .swagger-ui .opblock-description-wrapper p,
    [data-theme="dark"] .swagger-ui .opblock-description,
    .dark .swagger-ui .opblock-description,
    [data-theme="dark"] .swagger-ui .opblock-description p,
    .dark .swagger-ui .opblock-description p,
    [data-theme="dark"] .swagger-ui .opblock-external-docs-wrapper,
    .dark .swagger-ui .opblock-external-docs-wrapper,
    [data-theme="dark"] .swagger-ui .opblock-title_normal,
    .dark .swagger-ui .opblock-title_normal,
    [data-theme="dark"] .swagger-ui .opblock-title_normal p,
    .dark .swagger-ui .opblock-title_normal p,
    [data-theme="dark"] .swagger-ui .markdown,
    .dark .swagger-ui .markdown,
    [data-theme="dark"] .swagger-ui .markdown p,
    .dark .swagger-ui .markdown p,
    [data-theme="dark"] .swagger-ui .renderedMarkdown,
    .dark .swagger-ui .renderedMarkdown,
    [data-theme="dark"] .swagger-ui .renderedMarkdown p,
    .dark .swagger-ui .renderedMarkdown p,
    [data-theme="dark"] .swagger-ui .parameter__name,
    .dark .swagger-ui .parameter__name,
    [data-theme="dark"] .swagger-ui .parameter__type,
    .dark .swagger-ui .parameter__type,
    [data-theme="dark"] .swagger-ui .parameter__in,
    .dark .swagger-ui .parameter__in,
    [data-theme="dark"] .swagger-ui .parameter__extension,
    .dark .swagger-ui .parameter__extension,
    [data-theme="dark"] .swagger-ui .parameters-col_name,
    .dark .swagger-ui .parameters-col_name,
    [data-theme="dark"] .swagger-ui .parameters-col_description,
    .dark .swagger-ui .parameters-col_description,
    [data-theme="dark"] .swagger-ui .response-col_status,
    .dark .swagger-ui .response-col_status,
    [data-theme="dark"] .swagger-ui .response-col_description,
    .dark .swagger-ui .response-col_description,
    [data-theme="dark"] .swagger-ui .response-col_links,
    .dark .swagger-ui .response-col_links,
    [data-theme="dark"] .swagger-ui .response-col_links i,
    .dark .swagger-ui .response-col_links i,
    [data-theme="dark"] .swagger-ui .response-undocumented,
    .dark .swagger-ui .response-undocumented,
    [data-theme="dark"] .swagger-ui .opblock-section-header h4,
    .dark .swagger-ui .opblock-section-header h4,
    [data-theme="dark"] .swagger-ui .opblock-section-header label,
    .dark .swagger-ui .opblock-section-header label,
    [data-theme="dark"] .swagger-ui .responses-inner h4,
    .dark .swagger-ui .responses-inner h4,
    [data-theme="dark"] .swagger-ui .responses-inner h5,
    .dark .swagger-ui .responses-inner h5 {
      color: #ffffff !important;
    }

    /* LINKS IN SWAGGER */
    [data-theme="dark"] .swagger-ui a:not(.nav-btn):not(.swagger-btn),
    .dark .swagger-ui a:not(.nav-btn):not(.swagger-btn) {
      color: #60a5fa !important;
    }

    /* REQUIRED ASTERISK */
    [data-theme="dark"] .swagger-ui .parameter__name.required span,
    .dark .swagger-ui .parameter__name.required span,
    [data-theme="dark"] .swagger-ui .parameter__name.required:after,
    .dark .swagger-ui .parameter__name.required:after {
      color: #ef4444 !important;
    }

    /* TRY IT OUT BUTTON */
    [data-theme="dark"] .swagger-ui .btn.try-out__btn,
    .dark .swagger-ui .btn.try-out__btn {
      color: #ffffff !important;
      border: 1px solid #3b82f6 !important;
      background: rgba(59, 130, 246, 0.15) !important;
      border-radius: 6px !important;
      font-weight: 600 !important;
      transition: all 0.2s ease !important;
    }
    [data-theme="dark"] .swagger-ui .btn.try-out__btn:hover,
    .dark .swagger-ui .btn.try-out__btn:hover {
      background: #3b82f6 !important;
      color: #ffffff !important;
    }

    /* EXECUTE & CANCEL BUTTONS */
    [data-theme="dark"] .swagger-ui .btn.execute,
    .dark .swagger-ui .btn.execute {
      background-color: #3b82f6 !important;
      border-color: #3b82f6 !important;
      color: #ffffff !important;
      font-weight: 700 !important;
    }
    [data-theme="dark"] .swagger-ui .btn.execute:hover,
    .dark .swagger-ui .btn.execute:hover {
      background-color: #2563eb !important;
      border-color: #2563eb !important;
    }
    [data-theme="dark"] .swagger-ui .btn.btn-clear,
    .dark .swagger-ui .btn.btn-clear {
      color: #ffffff !important;
      border-color: #52525b !important;
      background: #27272a !important;
    }

    /* INPUTS & TEXTAREAS & PLACEHOLDERS */
    [data-theme="dark"] .swagger-ui input[type=text],
    [data-theme="dark"] .swagger-ui input[type=password],
    [data-theme="dark"] .swagger-ui textarea,
    .dark .swagger-ui input[type=text],
    .dark .swagger-ui input[type=password],
    .dark .swagger-ui textarea {
      background: #141414 !important;
      color: #ffffff !important;
      border: 1px solid #52525b !important;
      border-radius: 6px !important;
    }
    [data-theme="dark"] .swagger-ui input::placeholder,
    .dark .swagger-ui input::placeholder,
    [data-theme="dark"] .swagger-ui textarea::placeholder,
    .dark .swagger-ui textarea::placeholder {
      color: rgba(255, 255, 255, 0.75) !important;
    }

    /* ACCEPT CONTROL MESSAGE */
    [data-theme="dark"] .swagger-ui .response-control-media-type__accept-message,
    .dark .swagger-ui .response-control-media-type__accept-message {
      color: #86efac !important;
    }

    /* SERVERS SECTION */
    [data-theme="dark"] .swagger-ui .scheme-container,
    .dark .swagger-ui .scheme-container {
      background: #262626 !important;
      box-shadow: none !important;
      border-top: 1px solid #404040 !important;
      border-bottom: 1px solid #404040 !important;
      padding: 16px 0 !important;
      margin: 20px 0 !important;
    }
    [data-theme="dark"] .swagger-ui .scheme-container label,
    .dark .swagger-ui .scheme-container label {
      color: #ffffff !important;
      font-weight: 600 !important;
    }
    [data-theme="dark"] .swagger-ui select,
    .dark .swagger-ui select {
      background: #171717 !important;
      color: #ffffff !important;
      border: 1px solid #404040 !important;
      border-radius: 6px !important;
      padding: 8px 12px !important;
    }

    /* AUTHORIZE BUTTON */
    [data-theme="dark"] .swagger-ui .btn.authorize,
    .dark .swagger-ui .btn.authorize {
      color: #3b82f6 !important;
      border-color: #3b82f6 !important;
      background: rgba(59, 130, 246, 0.12) !important;
    }
    [data-theme="dark"] .swagger-ui .btn.authorize svg,
    .dark .swagger-ui .btn.authorize svg {
      fill: #3b82f6 !important;
    }

    /* TAGS & HEADINGS */
    [data-theme="dark"] .swagger-ui .opblock-tag,
    .dark .swagger-ui .opblock-tag {
      color: #ffffff !important;
      border-bottom: 1px solid #404040 !important;
    }
    [data-theme="dark"] .swagger-ui .opblock-tag:hover,
    .dark .swagger-ui .opblock-tag:hover {
      background: rgba(255, 255, 255, 0.04) !important;
    }
    [data-theme="dark"] .swagger-ui .opblock-tag small,
    .dark .swagger-ui .opblock-tag small {
      color: #ffffff !important;
    }

    /* OPERATION BLOCKS */
    [data-theme="dark"] .swagger-ui .opblock,
    .dark .swagger-ui .opblock {
      background: #262626 !important;
      border: 1px solid #404040 !important;
      border-radius: 8px !important;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3) !important;
      margin-bottom: 12px !important;
    }
    [data-theme="dark"] .swagger-ui .opblock .opblock-summary,
    .dark .swagger-ui .opblock .opblock-summary {
      border-color: transparent !important;
    }
    [data-theme="dark"] .swagger-ui .opblock .opblock-summary-path,
    .dark .swagger-ui .opblock .opblock-summary-path {
      color: #ffffff !important;
      font-weight: 700 !important;
    }
    [data-theme="dark"] .swagger-ui .opblock .opblock-summary-description,
    .dark .swagger-ui .opblock .opblock-summary-description {
      color: #ffffff !important;
    }

    /* METHOD BADGES & HIGHLIGHTS */
    [data-theme="dark"] .swagger-ui .opblock.opblock-get,
    .dark .swagger-ui .opblock.opblock-get {
      background: rgba(59, 130, 246, 0.08) !important;
      border-color: rgba(59, 130, 246, 0.35) !important;
    }
    [data-theme="dark"] .swagger-ui .opblock.opblock-get .opblock-summary-method,
    .dark .swagger-ui .opblock.opblock-get .opblock-summary-method {
      background: #3b82f6 !important;
      color: #ffffff !important;
    }
    [data-theme="dark"] .swagger-ui .opblock.opblock-post,
    .dark .swagger-ui .opblock.opblock-post {
      background: rgba(34, 197, 94, 0.08) !important;
      border-color: rgba(34, 197, 94, 0.35) !important;
    }
    [data-theme="dark"] .swagger-ui .opblock.opblock-post .opblock-summary-method,
    .dark .swagger-ui .opblock.opblock-post .opblock-summary-method {
      background: #22c55e !important;
      color: #ffffff !important;
    }
    [data-theme="dark"] .swagger-ui .opblock.opblock-put,
    .dark .swagger-ui .opblock.opblock-put {
      background: rgba(245, 158, 11, 0.08) !important;
      border-color: rgba(245, 158, 11, 0.35) !important;
    }
    [data-theme="dark"] .swagger-ui .opblock.opblock-put .opblock-summary-method,
    .dark .swagger-ui .opblock.opblock-put .opblock-summary-method {
      background: #f59e0b !important;
      color: #ffffff !important;
    }
    [data-theme="dark"] .swagger-ui .opblock.opblock-delete,
    .dark .swagger-ui .opblock.opblock-delete {
      background: rgba(239, 68, 68, 0.08) !important;
      border-color: rgba(239, 68, 68, 0.35) !important;
    }
    [data-theme="dark"] .swagger-ui .opblock.opblock-delete .opblock-summary-method,
    .dark .swagger-ui .opblock.opblock-delete .opblock-summary-method {
      background: #ef4444 !important;
      color: #ffffff !important;
    }

    /* EXPANDED OPBLOCK BODY & PARAMETERS */
    [data-theme="dark"] .swagger-ui .opblock-body,
    .dark .swagger-ui .opblock-body {
      background: #1c1c1c !important;
      color: #ffffff !important;
    }
    [data-theme="dark"] .swagger-ui .opblock-body pre,
    .dark .swagger-ui .opblock-body pre {
      background: #141414 !important;
      color: #ffffff !important;
      border: 1px solid #404040 !important;
    }
    [data-theme="dark"] .swagger-ui .opblock-section-header,
    .dark .swagger-ui .opblock-section-header {
      background: #262626 !important;
    }

    /* CODE & SYNTAX HIGHLIGHTING (MICROLIGHT) */
    [data-theme="dark"] .swagger-ui .microlight,
    .dark .swagger-ui .microlight,
    [data-theme="dark"] .swagger-ui .microlight *,
    .dark .swagger-ui .microlight * {
      color: #ffffff !important;
      background: transparent !important;
    }

    /* TAB LINKS */
    [data-theme="dark"] .swagger-ui .tab li button.tablinks,
    .dark .swagger-ui .tab li button.tablinks {
      color: #ffffff !important;
    }
    [data-theme="dark"] .swagger-ui .tab li button.tablinks.active,
    .dark .swagger-ui .tab li button.tablinks.active {
      color: #60a5fa !important;
      border-bottom: 2px solid #60a5fa !important;
      font-weight: 700 !important;
    }

    /* AUTHORIZE MODAL */
    [data-theme="dark"] .swagger-ui .dialog-ux .backdrop-ux,
    .dark .swagger-ui .dialog-ux .backdrop-ux {
      background: rgba(0, 0, 0, 0.75) !important;
    }
    [data-theme="dark"] .swagger-ui .dialog-ux .modal-ux,
    .dark .swagger-ui .dialog-ux .modal-ux {
      background: #262626 !important;
      border: 1px solid #404040 !important;
      color: #ffffff !important;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5) !important;
    }
    [data-theme="dark"] .swagger-ui .dialog-ux .modal-ux-header,
    .dark .swagger-ui .dialog-ux .modal-ux-header {
      border-bottom: 1px solid #404040 !important;
    }
    [data-theme="dark"] .swagger-ui .dialog-ux .modal-ux-header h3,
    .dark .swagger-ui .dialog-ux .modal-ux-header h3 {
      color: #ffffff !important;
    }
    [data-theme="dark"] .swagger-ui .dialog-ux .modal-ux-content,
    .dark .swagger-ui .dialog-ux .modal-ux-content {
      color: #ffffff !important;
    }
    [data-theme="dark"] .swagger-ui .dialog-ux .modal-ux-content h4,
    .dark .swagger-ui .dialog-ux .modal-ux-content h4 {
      color: #ffffff !important;
    }
    [data-theme="dark"] .swagger-ui .dialog-ux .modal-ux-content p,
    .dark .swagger-ui .dialog-ux .modal-ux-content p {
      color: #ffffff !important;
    }

    /* UNIFIED ACTION BUTTONS ACROSS ALL INTERFACES */
    .nav-btn,
    .swagger-btn {
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      gap: 7px !important;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
      font-weight: 600 !important;
      font-size: 13px !important;
      padding: 7px 14px !important;
      border-radius: 8px !important;
      text-decoration: none !important;
      box-shadow: 0 1px 3px rgba(0,0,0,0.15) !important;
      transition: all 0.18s ease !important;
      cursor: pointer !important;
      background: #5b95cb !important;
      color: #ffffff !important;
      border: 1px solid #5b95cb !important;
      white-space: nowrap !important;
    }
    .nav-btn:hover,
    .swagger-btn:hover {
      background: #4f89be !important;
      border-color: #4f89be !important;
      color: #ffffff !important;
      box-shadow: 0 4px 12px rgba(91, 149, 203, 0.3) !important;
      transform: translateY(-1px);
    }
    .nav-btn.active,
    .swagger-btn.active {
      background: #396a97 !important;
      border-color: #305c83 !important;
      color: #ffffff !important;
      box-shadow: inset 0 2px 4px rgba(0,0,0,0.25) !important;
    }

    /* Guarantee pure white text regardless of parent anchor styling */
    .dark .nav-btn,
    .dark .swagger-btn,
    [data-theme="dark"] .nav-btn,
    [data-theme="dark"] .swagger-btn,
    .swagger-ui .info a.nav-btn,
    .swagger-ui .info a.swagger-btn,
    .dark .swagger-ui .info a.nav-btn,
    .dark .swagger-ui .info a.swagger-btn,
    [data-theme="dark"] .swagger-ui .info a.nav-btn,
    [data-theme="dark"] .swagger-ui .info a.swagger-btn {
      color: #ffffff !important;
      background: #4f89be !important;
      border: 1px solid #4f89be !important;
    }
    .dark .nav-btn:hover,
    .dark .swagger-btn:hover,
    [data-theme="dark"] .nav-btn:hover,
    [data-theme="dark"] .swagger-btn:hover,
    .dark .swagger-ui .info a.nav-btn:hover,
    .dark .swagger-ui .info a.swagger-btn:hover,
    [data-theme="dark"] .swagger-ui .info a.nav-btn:hover,
    [data-theme="dark"] .swagger-ui .info a.swagger-btn:hover {
      color: #ffffff !important;
      background: #5b95cb !important;
      border-color: #5b95cb !important;
    }
    .dark .nav-btn.active,
    .dark .swagger-btn.active,
    [data-theme="dark"] .nav-btn.active,
    [data-theme="dark"] .swagger-btn.active {
      background: #396a97 !important;
      border-color: #305c83 !important;
      color: #ffffff !important;
    }
    #swagger-theme-toggle,
    #theme-toggle {
      padding: 5px 9px !important;
    }
    .theme-icon,
    [data-theme="dark"] .theme-icon,
    .dark .theme-icon,
    [data-theme="dark"] .swagger-ui .theme-icon,
    .dark .swagger-ui .theme-icon,
    [data-theme="dark"] #swagger-theme-toggle .theme-icon,
    .dark #swagger-theme-toggle .theme-icon {
      width: 26px !important;
      height: 21px !important;
      object-fit: contain !important;
      display: block !important;
      filter: brightness(0) invert(1) !important;
      pointer-events: none !important;
    }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js"></script>
  <script>
    // --- UNIFIED THEME SYSTEM ---
    function initTheme() {
      const saved = localStorage.getItem('theme');
      if (saved) {
        setTheme(saved, false);
      } else {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        setTheme(prefersDark ? 'dark' : 'light', false);
      }

      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem('theme')) {
          setTheme(e.matches ? 'dark' : 'light', false);
        }
      });
    }

    function setTheme(theme, save = true) {
      document.documentElement.setAttribute('data-theme', theme);
      document.documentElement.classList.toggle('dark', theme === 'dark');
      if (save) localStorage.setItem('theme', theme);
    }

    function injectFlashBanner() {
      const info = document.querySelector('.swagger-ui .info');
      if (info && !document.getElementById('flash-header-banner')) {
        const banner = document.createElement('div');
        banner.id = 'flash-header-banner';
        banner.title = 'Flash Server';
        banner.innerHTML = '<img src="/static/flash.gif" alt="Flash Animation" />';
        info.appendChild(banner);

        const actionContainer = document.createElement('div');
        actionContainer.id = 'swagger-action-bar';
        actionContainer.style = 'margin-top: 16px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;';

        actionContainer.innerHTML = `
          <a href="/docs" class="nav-btn active" title="Swagger API Documentation">Docs</a>
          <a href="/tutoring" class="nav-btn" title="Crossroads Tutoring Console">Tutoring Calc</a>
          <a href="/monitoring" class="nav-btn" title="Flash Server Monitoring">System Monitor</a>
          <a href="/todo" class="nav-btn" title="Crossroads To-Do Board">To Do</a>
          <a href="/invoices" class="nav-btn" title="Invoice Generator & History">Invoices</a>
          <a href="/finance" class="nav-btn" title="Financial Dashboard & SimpleFIN">Finance</a>
          <button id="swagger-theme-toggle" class="nav-btn" aria-label="Toggle Theme" title="Toggle Theme">
            <img src="/static/day-and-night.svg" alt="Theme" class="theme-icon" />
          </button>
        `;
        info.appendChild(actionContainer);

        document.getElementById('swagger-theme-toggle').addEventListener('click', () => {
          const theme = document.documentElement.getAttribute('data-theme') || 'light';
          setTheme(theme === 'dark' ? 'light' : 'dark', true);
        });
      }
    }

    window.onload = function() {
      initTheme();

      window.ui = SwaggerUIBundle({
        url: "/openapi.json",
        dom_id: '#swagger-ui',
        deepLinking: true,
        persistAuthorization: true,
        validatorUrl: null,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        layout: "StandaloneLayout",
        onComplete: function() {
          injectFlashBanner();
        }
      });

      const swaggerContainer = document.getElementById('swagger-ui');
      if (swaggerContainer) {
        const observer = new MutationObserver(() => {
          injectFlashBanner();
        });
        observer.observe(swaggerContainer, { childList: true, subtree: true });
      }

      const timer = setInterval(injectFlashBanner, 150);
      setTimeout(() => clearInterval(timer), 3500);
    };
  </script>
</body>
</html>
"""


@swagger_bp.route("/")
@swagger_bp.route("/docs")
def swagger_ui():
    return render_template_string(SWAGGER_HTML_TEMPLATE)


@swagger_bp.route("/openapi.json")
@swagger_bp.route("/swagger.json")
def openapi_spec():
    return jsonify(OPENAPI_SPEC)


@swagger_bp.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(BASE_DIR, 'index', 'static'), 'flash.png', mimetype='image/png')
