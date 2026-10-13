# ToDo Module

The `ToDo` package provides an interactive task management board organized across custom categories, drag-and-drop task reordering, one-click archival, and SQLite persistence.

Accessible at `http://localhost:5000/todo`.

---

## 1. Features & Architecture

* **Responsive Category Grid**: Tasks are organized into customizable category cards. Categories can be dynamically added, edited, reordered, or archived.
* **Weekday & Task Size Tags**: Supports assigning day-of-week tags (`Sunday` - `Saturday`) and size tags (`Small`, `Medium`, `Long`) to categorize workload and schedule tasks.
* **Eisenhower & Priority Sorting**: Supports priority indicators, task due dates, completion toggles, and drag-and-drop manual reordering that saves directly to backend indices.
* **Manual & Bulk Operations**: Instant one-click actions: "Archive Completed", "Restore Task", "View Archive", and "Archived Categories" viewer with conflict resolution safeguards.
* **SQLite WAL Mode Engine**: All tasks and categories are stored in `data/tasks.db` with Write-Ahead Logging (`WAL`), supporting high concurrency and atomic transactions.
* **REST API & Swagger Specs**: Fully documented OpenAPI 3.0 endpoints with HTTP Basic Authentication.

---

## 2. Endpoints Reference

All endpoints are protected by HTTP Basic Authentication.

### Web Dashboard
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/todo` | `GET` | Interactive To-Do board interface with category management and archive views. |

### Tasks API
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /api/todo/items` | `GET` | Retrieves active or archived tasks (`?status=active|archived`). |
| `POST /api/todo/items` | `POST` | Creates a new task in a specified category with optional `day_tag` and `size_tag`. |
| `PATCH /api/todo/items/<id>` | `PATCH` | Updates task text, category, completion status, `day_tag`, or `size_tag`. |
| `DELETE /api/todo/items/<id>` | `DELETE`| Permanently deletes an individual task. |
| `POST /api/todo/reorder` | `POST` | Reorders tasks within a category by persisting an array of task IDs in sequence. |
| `POST /api/todo/archive-completed` | `POST` | Manually archives all currently completed tasks immediately. |
| `POST /api/todo/archive-all` | `POST` | Archives all active tasks regardless of completion. |
| `POST /api/todo/items/<id>/restore` | `POST` | Restores an archived task back to active status. |
| `POST /api/todo/delete-all` | `POST` | Permanently deletes all tasks of a given `status` (default `active`), optionally for one `category`. |

### Categories API
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /api/todo/categories` | `GET` | Lists all active categories with their custom statuses and sort orders. |
| `POST /api/todo/categories` | `POST` | Creates a new category. Detects soft-archived duplicate names and offers restoration. |
| `PATCH /api/todo/categories/<id>` | `PATCH` | Updates category name, color theme, or sort order. |
| `POST /api/todo/categories/<id>/archive` | `POST` | Archives a category along with all of its contained tasks. |
| `POST /api/todo/categories/<id>/restore` | `POST` | Restores an archived category and its tasks back to the active board. |
| `GET /api/todo/categories/archived-summary` | `GET` | Retrieves all archived categories and their associated tasks summary. |

---

## 3. Database Schema

Stored in `data/tasks.db`:

```
  ┌───────────────────────────────────────────────────────────┐
  │                        categories                         │
  ├───────────────────────────────────────────────────────────┤
  │ id (INTEGER PRIMARY KEY AUTOINCREMENT)                    │
  │ name (TEXT NOT NULL UNIQUE COLLATE NOCASE)                │
  │ color (TEXT NOT NULL DEFAULT '#6ba3d6')                   │
  │ status (TEXT NOT NULL DEFAULT 'active')                   │
  │ custom_status (TEXT NOT NULL DEFAULT '')                  │
  │ display_order (INTEGER DEFAULT 0)                         │
  │ created_at (TEXT NOT NULL)                                │
  └─────────────────────────────┬─────────────────────────────┘
                                │ 1:N (CASCADE)
                                ▼
  ┌───────────────────────────────────────────────────────────┐
  │                           tasks                           │
  ├───────────────────────────────────────────────────────────┤
  │ id (INTEGER PRIMARY KEY AUTOINCREMENT)                    │
  │ category (TEXT NOT NULL)                                  │
  │ text (TEXT NOT NULL)                                      │
  │ completed (INTEGER DEFAULT 0)                             │
  │ completed_at (TEXT)                                       │
  │ status (TEXT DEFAULT 'active')                            │
  │ display_order (INTEGER DEFAULT 0)                         │
  │ archived_at (TEXT)                                        │
  │ created_at (TEXT NOT NULL)                                │
  │ day_tag (TEXT DEFAULT '')                                 │
  │ size_tag (TEXT DEFAULT '')                                │
  └───────────────────────────────────────────────────────────┘
```

---

## 4. Package Structure

```
ToDo/
├── __init__.py                # Blueprint export (todo_bp)
├── config.py                  # Default categories fallback & timezone settings
├── db.py                      # SQLite WAL database layer and migrations
├── routes.py                  # Web & REST API endpoints for tasks and categories
│   └── todo.html              # Responsive board UI with drag-and-drop and dark mode
├── tests/
│   ├── __init__.py            # Test package marker
│   ├── test_todo.py           # CRUD, reordering, categories, and archiving (real DB, [TEST] rows)
│   └── test_todo_isolated.py  # Ordering rules, validation, migrations, and every route (temp DB)
└── README.md                  # Module technical reference
```

---

## 5. Automated Testing

Run all unit tests for the To-Do module:

```bash
# From repository root
.venv/bin/python -m unittest discover -s modules/ToDo/tests -p "test_*.py"
```

Deeper documentation: [docs/ToDo/](../../docs/ToDo/)
