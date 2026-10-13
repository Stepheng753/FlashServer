# ToDo Architecture

Source: [modules/ToDo/](../../modules/ToDo/). Overview and endpoint list: [module README](../../modules/ToDo/README.md).

| File | Responsibility |
| :--- | :--- |
| `config.py` | `data/tasks.db` path, timezone (`America/Los_Angeles`), `DEFAULT_CATEGORIES` fallback. |
| `db.py` | Schema, migrations, category and task operations. |
| `routes.py` | `todo_bp` blueprint. Calls `init_db()` at import time. |
| `todo.html` | Board UI with drag-and-drop. |

---

## 1. Data model (`data/tasks.db`)

* **`categories`**: `name` (unique, case-insensitive), `color` (hex), `status` (`active` / `archived`), `custom_status` (free text shown on the card), `display_order`.
* **`tasks`**: `category` (the category *name*), `text`, `completed`, `status` (`active` / `archived`), `display_order`, `day_tag`, `size_tag`, and the `completed_at`, `archived_at`, `created_at` timestamps.

`init_db()` creates the tables, adds missing columns on older databases, and seeds the default categories when the table is empty.

---

## 2. Ordering rules

Active tasks in a category are kept in two groups: uncompleted first, completed after.

* **New tasks** go to the end of the uncompleted group, above completed tasks.
* **Restored tasks** come back uncompleted and are placed the same way.
* `get_tasks("active")` renumbers `display_order` so the values stay contiguous.
* `POST /api/todo/reorder` takes `{"items": [...]}` and writes the new order (and category) for each item.

---

## 3. Archiving

| Action | Effect |
| :--- | :--- |
| `POST /api/todo/archive-completed` | Completed active tasks become `archived`. |
| `POST /api/todo/archive-all` | All active tasks (optionally for one `category`) become `archived`. |
| `POST /api/todo/categories/<id>/archive` | The category becomes `archived`, and its active tasks are archived **and marked completed**. |
| `POST /api/todo/categories/<id>/restore` | The category is active again. Its old tasks stay archived and reappear in the archive view. |
| `POST /api/todo/items/<id>/restore` | One task goes back to the active board. |
| `POST /api/todo/delete-all` | Permanently deletes every task with the given `status` (body, default `active`), optionally limited to one `category`. |

Archiving is always manual: tasks are only archived when one of the endpoints above is called. There is no scheduled or automatic rollover.

---

## 4. Categories

* Names are unique case-insensitively. Creating one that already exists and is active returns `400`.
* Creating one whose archived twin exists returns `409` with `"conflict": "archived"` and the archived category, so the UI can offer to restore it.
* Colors must be 3, 6 or 8 digit hex (the leading `#` is optional).
* `PATCH /api/todo/categories/<id>` can rename, recolor, reorder, or change `custom_status`. Renaming moves the tasks with it.
* There is **no HTTP route to delete a category**. The UI archives them instead. `delete_category()` exists in `db.py` and removes only the category row. It does not touch tasks, so tasks with that category name would be left behind.

---

## 5. Tags

`day_tag` holds a weekday name and `size_tag` holds `Small`, `Medium` or `Long`. Both are free text at the database level, trimmed on write, and optional. Sending an empty string clears a tag.
