import sqlite3
import os
import re
from datetime import datetime, timedelta
import pytz
from .config import DB_PATH, APP_TIMEZONE, DEFAULT_CATEGORIES

HEX_COLOR_REGEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def get_connection():
    """Returns a SQLite connection with Row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the tasks and categories tables and migrates if needed."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                text TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                completed_at TEXT,
                status TEXT DEFAULT 'active',
                display_order INTEGER DEFAULT 0,
                archived_at TEXT,
                created_at TEXT NOT NULL,
                day_tag TEXT DEFAULT '',
                size_tag TEXT DEFAULT ''
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                color TEXT NOT NULL DEFAULT '#6ba3d6',
                status TEXT NOT NULL DEFAULT 'active',
                custom_status TEXT NOT NULL DEFAULT '',
                display_order INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
        """)
        # Indexes for query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_order ON tasks(category, display_order);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_order ON categories(display_order);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_status ON categories(status);")
        conn.commit()

        # Schema evolution: Ensure custom_status exists on existing tables
        cursor.execute("PRAGMA table_info(categories);")
        col_names = [r["name"] for r in cursor.fetchall()]
        if "custom_status" not in col_names:
            cursor.execute("ALTER TABLE categories ADD COLUMN custom_status TEXT NOT NULL DEFAULT '';")
            cursor.execute("UPDATE categories SET custom_status = status WHERE status != 'active' AND status != 'archived';")
            cursor.execute("UPDATE categories SET status = 'active' WHERE status != 'active' AND status != 'archived';")
            conn.commit()

        # Schema evolution: Ensure day_tag and size_tag exist on tasks table
        cursor.execute("PRAGMA table_info(tasks);")
        task_col_names = [r["name"] for r in cursor.fetchall()]
        if "day_tag" not in task_col_names:
            cursor.execute("ALTER TABLE tasks ADD COLUMN day_tag TEXT DEFAULT '';")
            conn.commit()
        if "size_tag" not in task_col_names:
            cursor.execute("ALTER TABLE tasks ADD COLUMN size_tag TEXT DEFAULT '';")
            conn.commit()

        # Seed default categories if table is empty
        seed_default_categories_if_needed(conn)

        # Drop legacy category_statuses table (now superseded by categories.custom_status column)
        cursor.execute("DROP TABLE IF EXISTS category_statuses;")
        conn.commit()

    normalize_active_tasks_order()




def normalize_active_tasks_order():
    """
    Ensures that active tasks within each category maintain proper order:
    all uncompleted tasks come first (ordered by display_order, id),
    followed by all completed tasks (ordered by display_order, id).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM tasks WHERE status = 'active'")
        categories = [r["category"] for r in cursor.fetchall()]

        for cat in categories:
            cursor.execute("""
                SELECT id, completed, display_order FROM tasks
                WHERE category = ? AND status = 'active'
                ORDER BY completed ASC, display_order ASC, id ASC
            """, (cat,))
            tasks = cursor.fetchall()
            for idx, r in enumerate(tasks, start=1):
                if r["display_order"] != idx:
                    cursor.execute("UPDATE tasks SET display_order = ? WHERE id = ?", (idx, r["id"]))
        conn.commit()


def seed_default_categories_if_needed(conn):
    """
    Seeds DEFAULT_CATEGORIES into the SQLite categories table if the table is empty.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM categories")
    row = cursor.fetchone()
    if row and row["cnt"] > 0:
        return

    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    order = 1
    for c in DEFAULT_CATEGORIES:
        cursor.execute("""
            INSERT OR IGNORE INTO categories (name, color, status, custom_status, display_order, created_at)
            VALUES (?, ?, 'active', '', ?, ?)
        """, (c["name"], c.get("color", "#6ba3d6"), order, now_iso))
        order += 1

    conn.commit()
    print(f"[ToDo] Seeded {len(DEFAULT_CATEGORIES)} default categories into categories table.")


class CategoryArchivedConflict(Exception):
    """Raised when attempting to create a category whose name collides with an archived category."""
    def __init__(self, category):
        self.category = category
        super().__init__(f"Category '{category['name']}' is currently archived.")


def category_row_to_dict(row):
    """Converts a SQLite categories row to dictionary."""
    custom_st = ""
    if "custom_status" in row.keys() and row["custom_status"] is not None:
        custom_st = row["custom_status"]
    return {
        "id": row["id"],
        "name": row["name"],
        "color": row["color"],
        "status": row["status"],
        "custom_status": custom_st,
        "status_text": custom_st,
        "display_order": row["display_order"],
        "created_at": row["created_at"]
    }


def get_categories(status="active"):
    """
    Retrieves categories from SQLite ordered by display_order, id.
    status can be 'active', 'archived', or 'all'.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if status in ("active", "archived"):
            cursor.execute("SELECT * FROM categories WHERE status = ? ORDER BY display_order ASC, id ASC", (status,))
        else:
            cursor.execute("SELECT * FROM categories ORDER BY display_order ASC, id ASC")
        return [category_row_to_dict(r) for r in cursor.fetchall()]


def get_category_by_id(category_id):
    """Retrieves a single category by id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        row = cursor.fetchone()
        return category_row_to_dict(row) if row else None


def get_category_by_name(name):
    """Retrieves a single category by name (case-insensitive)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE name = ? COLLATE NOCASE", (name.strip(),))
        row = cursor.fetchone()
        return category_row_to_dict(row) if row else None


def add_category(name, color=None):
    """
    Adds a new category to SQLite.
    Raises ValueError if name is empty or already exists as an active category.
    Raises CategoryArchivedConflict if category exists in archived state.
    """
    name = (name or "").strip()
    color = (color or "#5b95cb").strip()
    if not name:
        raise ValueError("Category name cannot be empty.")

    if not color.startswith("#"):
        color = f"#{color}"
    if not HEX_COLOR_REGEX.match(color):
        raise ValueError(f"Invalid hex color format: '{color}'. Expected 3, 6, or 8 digit hex color (e.g. #5b95cb).")

    now_iso = datetime.now(APP_TIMEZONE).isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        # Check existing category
        cursor.execute("SELECT * FROM categories WHERE name = ? COLLATE NOCASE", (name,))
        existing = cursor.fetchone()
        if existing:
            existing_dict = category_row_to_dict(existing)
            if existing_dict["status"] == "active":
                raise ValueError(f"Category '{name}' already exists.")
            elif existing_dict["status"] == "archived":
                raise CategoryArchivedConflict(existing_dict)

        cursor.execute("SELECT COALESCE(MAX(display_order), 0) as max_ord FROM categories")
        next_order = (cursor.fetchone()["max_ord"] or 0) + 1

        cursor.execute("""
            INSERT INTO categories (name, color, status, custom_status, display_order, created_at)
            VALUES (?, ?, 'active', '', ?, ?)
        """, (name, color, next_order, now_iso))
        conn.commit()
        cat_id = cursor.lastrowid

    return get_category_by_id(cat_id)


def update_category(category_id, name=None, color=None, status=None, custom_status=None, display_order=None):
    """
    Updates category attributes. If name changes, updates associated tasks as well.
    """
    current = get_category_by_id(category_id)
    if not current:
        return None

    updates = []
    params = []
    old_name = current["name"]
    name_changed = False
    trimmed_name = None

    if name is not None:
        trimmed_name = name.strip()
        if not trimmed_name:
            raise ValueError("Category name cannot be empty.")
        if trimmed_name.lower() != old_name.lower():
            existing = get_category_by_name(trimmed_name)
            if existing and existing["id"] != category_id:
                raise ValueError(f"Category '{trimmed_name}' already exists.")
            name_changed = True
        updates.append("name = ?")
        params.append(trimmed_name)

    if color is not None:
        trimmed_color = color.strip()
        if not trimmed_color.startswith("#"):
            trimmed_color = f"#{trimmed_color}"
        if not HEX_COLOR_REGEX.match(trimmed_color):
            raise ValueError(f"Invalid hex color format: '{trimmed_color}'. Expected 3, 6, or 8 digit hex color (e.g. #5b95cb).")
        updates.append("color = ?")
        params.append(trimmed_color)

    if status is not None:
        status_val = status.strip().lower()
        if status_val not in ("active", "archived"):
            raise ValueError(f"Invalid category status: '{status}'. Expected 'active' or 'archived'.")
        updates.append("status = ?")
        params.append(status_val)

    if custom_status is not None:
        updates.append("custom_status = ?")
        params.append(custom_status.strip())

    if display_order is not None:
        updates.append("display_order = ?")
        params.append(int(display_order))

    if not updates:
        return current

    params.append(category_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = ?", params)
        if name_changed and trimmed_name:
            cursor.execute("UPDATE tasks SET category = ? WHERE category = ?", (trimmed_name, old_name))
        conn.commit()

    return get_category_by_id(category_id)


def archive_category(category_id):
    """
    Archives a category and cascades to automatically archive all its active tasks.
    Returns dict with updated category and count of tasks archived.
    """
    cat = get_category_by_id(category_id)
    if not cat:
        return None

    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE categories SET status = 'archived' WHERE id = ?", (category_id,))
        cursor.execute("""
            UPDATE tasks
            SET status = 'archived', completed = 1, completed_at = COALESCE(completed_at, ?), archived_at = ?
            WHERE category = ? AND status = 'active'
        """, (now_iso, now_iso, cat["name"]))
        tasks_archived = cursor.rowcount
        conn.commit()

    return {
        "category": get_category_by_id(category_id),
        "tasks_archived": tasks_archived
    }


def restore_category(category_id, color=None):
    """
    Restores an archived category to active status.
    All historical tasks of this category remain archived (status = 'archived'),
    which will now repopulate the category's column in the Archive View.
    """
    cat = get_category_by_id(category_id)
    if not cat:
        return None

    updates = ["status = 'active'"]
    params = []

    if color:
        c_strip = color.strip()
        if not c_strip.startswith("#"):
            c_strip = f"#{c_strip}"
        if HEX_COLOR_REGEX.match(c_strip):
            updates.append("color = ?")
            params.append(c_strip)

    params.append(category_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE categories SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    return get_category_by_id(category_id)


def get_archived_categories_with_tasks():
    """
    Returns list of all archived categories and their archived tasks.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM categories WHERE status = 'archived' ORDER BY display_order ASC, id ASC")
        cat_rows = cursor.fetchall()
        categories = [category_row_to_dict(r) for r in cat_rows]

        for cat in categories:
            cursor.execute("""
                SELECT * FROM tasks
                WHERE category = ? AND status = 'archived'
                ORDER BY completed ASC, display_order ASC, id ASC
            """, (cat["name"],))
            cat["tasks"] = [task_row_to_dict(t) for t in cursor.fetchall()]
            cat["task_count"] = len(cat["tasks"])

        return categories


def delete_category(category_id):
    """Deletes a category by id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        count = cursor.rowcount
        conn.commit()
    return count > 0


def get_categories_with_status():
    """Alias for get_categories(status='active') for backwards compatibility."""
    return get_categories(status="active")


def set_category_status(category, status):
    """
    Persists category custom status bar text directly to SQLite categories.custom_status column.
    """
    category = (category or "").strip()
    status_text = (status or "").strip()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE categories SET custom_status = ? WHERE name = ? COLLATE NOCASE",
            (status_text, category)
        )
        conn.commit()

    cat = get_category_by_name(category)
    return cat if cat else {"id": category, "name": category, "color": "#6ba3d6", "status": "active", "custom_status": status_text, "status_text": status_text}


def task_row_to_dict(row):
    """Converts a sqlite3.Row to a clean Python dictionary."""
    day_tag = ""
    if "day_tag" in row.keys() and row["day_tag"] is not None:
        day_tag = str(row["day_tag"])
    size_tag = ""
    if "size_tag" in row.keys() and row["size_tag"] is not None:
        size_tag = str(row["size_tag"])
    return {
        "id": row["id"],
        "category": row["category"],
        "text": row["text"],
        "completed": bool(row["completed"]),
        "completed_at": row["completed_at"],
        "status": row["status"],
        "display_order": row["display_order"],
        "archived_at": row["archived_at"],
        "created_at": row["created_at"],
        "day_tag": day_tag,
        "size_tag": size_tag
    }


def get_tasks(status="active", category=None):
    """
    Retrieves tasks by status ('active' or 'archived'), optionally filtered by category.
    """
    if status == "active":
        normalize_active_tasks_order()

    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM tasks WHERE status = ?"
        params = [status]

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " ORDER BY display_order ASC, id ASC"
        cursor.execute(query, params)
        return [task_row_to_dict(row) for row in cursor.fetchall()]


def get_task_by_id(task_id):
    """Retrieves a single task by its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return task_row_to_dict(row) if row else None


def add_task(text, category, day_tag="", size_tag=""):
    """Adds a new active task to a category, always placed above completed tasks."""
    text = (text or "").strip()
    category = (category or "Misc").strip()
    day_tag_val = (day_tag or "").strip()
    size_tag_val = (size_tag or "").strip()
    if not text:
        raise ValueError("Task text cannot be empty.")

    now_iso = datetime.now(APP_TIMEZONE).isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        # Fetch existing active tasks in this category
        cursor.execute("""
            SELECT id, completed, display_order FROM tasks
            WHERE category = ? AND status = 'active'
            ORDER BY completed ASC, display_order ASC, id ASC
        """, (category,))
        existing = cursor.fetchall()

        uncompleted_ids = [r["id"] for r in existing if not r["completed"]]
        completed_ids = [r["id"] for r in existing if r["completed"]]

        new_order = len(uncompleted_ids) + 1

        cursor.execute("""
            INSERT INTO tasks (category, text, completed, status, display_order, created_at, day_tag, size_tag)
            VALUES (?, ?, 0, 'active', ?, ?, ?, ?)
        """, (category, text, new_order, now_iso, day_tag_val, size_tag_val))
        task_id = cursor.lastrowid

        # Normalize uncompleted tasks before new task
        for idx, tid in enumerate(uncompleted_ids, start=1):
            cursor.execute("UPDATE tasks SET display_order = ? WHERE id = ?", (idx, tid))

        # Shift all completed tasks after new task
        for idx, tid in enumerate(completed_ids, start=new_order + 1):
            cursor.execute("UPDATE tasks SET display_order = ? WHERE id = ?", (idx, tid))

        conn.commit()

    return get_task_by_id(task_id)


def update_task(task_id, text=None, category=None, completed=None, display_order=None, day_tag=None, size_tag=None):
    """Updates a task's text, category, completion status, display order, day tag, or size tag."""
    task = get_task_by_id(task_id)
    if not task:
        return None

    updates = []
    params = []

    if text is not None:
        trimmed = text.strip()
        if not trimmed:
            raise ValueError("Task text cannot be empty.")
        updates.append("text = ?")
        params.append(trimmed)

    if category is not None:
        trimmed_cat = category.strip()
        if trimmed_cat:
            updates.append("category = ?")
            params.append(trimmed_cat)

    if completed is not None:
        is_comp = 1 if completed else 0
        updates.append("completed = ?")
        params.append(is_comp)
        if is_comp:
            updates.append("completed_at = ?")
            params.append(datetime.now(APP_TIMEZONE).isoformat())
        else:
            updates.append("completed_at = NULL")

    if display_order is not None:
        updates.append("display_order = ?")
        params.append(int(display_order))

    if day_tag is not None:
        updates.append("day_tag = ?")
        params.append(day_tag.strip() if isinstance(day_tag, str) else "")

    if size_tag is not None:
        updates.append("size_tag = ?")
        params.append(size_tag.strip() if isinstance(size_tag, str) else "")

    if not updates:
        return task

    params.append(task_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    return get_task_by_id(task_id)


def reorder_tasks(items):
    """
    Batch updates tasks display_order and optional category.
    items: list of dicts [{'id': int, 'display_order': int, 'category': str (optional)}]
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        for item in items:
            tid = item.get("id")
            order = item.get("display_order", 0)
            cat = item.get("category")
            if cat:
                cursor.execute(
                    "UPDATE tasks SET display_order = ?, category = ? WHERE id = ?",
                    (order, cat, tid)
                )
            else:
                cursor.execute(
                    "UPDATE tasks SET display_order = ? WHERE id = ?",
                    (order, tid)
                )
        conn.commit()
    return True


def archive_completed_now():
    """Immediately moves all completed active tasks to status = 'archived'."""
    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tasks
            SET status = 'archived', archived_at = ?
            WHERE status = 'active' AND completed = 1
        """, (now_iso,))
        count = cursor.rowcount
        conn.commit()
    return count


def archive_all(category=None):
    """Archives all active tasks, optionally for a specific category."""
    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "UPDATE tasks SET status = 'archived', archived_at = ? WHERE status = 'active'"
        params = [now_iso]
        if category:
            query += " AND category = ?"
            params.append(category)
        cursor.execute(query, params)
        count = cursor.rowcount
        conn.commit()
    return count


def restore_task(task_id):
    """Restores an archived task back to active status (uncompleted), placed above completed tasks."""
    task = get_task_by_id(task_id)
    if not task:
        return None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, completed, display_order FROM tasks
            WHERE category = ? AND status = 'active'
            ORDER BY completed ASC, display_order ASC, id ASC
        """, (task["category"],))
        existing = cursor.fetchall()

        uncompleted_ids = [r["id"] for r in existing if not r["completed"]]
        completed_ids = [r["id"] for r in existing if r["completed"]]

        new_order = len(uncompleted_ids) + 1

        cursor.execute("""
            UPDATE tasks
            SET status = 'active', completed = 0, completed_at = NULL, archived_at = NULL, display_order = ?
            WHERE id = ?
        """, (new_order, task_id))

        for idx, tid in enumerate(uncompleted_ids, start=1):
            cursor.execute("UPDATE tasks SET display_order = ? WHERE id = ?", (idx, tid))

        for idx, tid in enumerate(completed_ids, start=new_order + 1):
            cursor.execute("UPDATE tasks SET display_order = ? WHERE id = ?", (idx, tid))

        conn.commit()

    return get_task_by_id(task_id)


def delete_task(task_id):
    """Permanently deletes a task by id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        count = cursor.rowcount
        conn.commit()
    return count > 0


def delete_all(status="active", category=None):
    """Permanently deletes tasks filtered by status and optional category."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "DELETE FROM tasks WHERE status = ?"
        params = [status]
        if category:
            query += " AND category = ?"
            params.append(category)
        cursor.execute(query, params)
        count = cursor.rowcount
        conn.commit()
    return count
