import os
import sys
import unittest
from datetime import datetime, timedelta
import pytz

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.ToDo.config import load_categories, APP_TIMEZONE
from modules.ToDo.db import (
    init_db,
    get_connection,
    get_tasks,
    add_task,
    update_task,
    reorder_tasks,
    archive_completed_now,
    archive_all,
    restore_task,
    delete_task,
    delete_all,
    get_categories,
    get_category_by_id,
    get_category_by_name,
    add_category,
    update_category,
    delete_category,
    archive_category,
    restore_category,
    get_archived_categories_with_tasks,
    CategoryArchivedConflict,
    set_category_status,
    get_categories_with_status
)
from app import app


class TestToDoApp(unittest.TestCase):

    def setUp(self):
        init_db()
        # Clean test state
        with get_connection() as conn:
            conn.cursor().execute("DELETE FROM tasks WHERE text LIKE '[TEST]%'")
            conn.cursor().execute("DELETE FROM categories WHERE name LIKE '[TEST]%'")
            conn.commit()

    def tearDown(self):
        with get_connection() as conn:
            conn.cursor().execute("DELETE FROM tasks WHERE text LIKE '[TEST]%'")
            conn.cursor().execute("DELETE FROM categories WHERE name LIKE '[TEST]%'")
            conn.commit()

    def test_load_categories(self):
        from modules.ToDo.config import DEFAULT_CATEGORIES
        self.assertEqual(len(DEFAULT_CATEGORIES), 7)
        self.assertEqual(DEFAULT_CATEGORIES[0]["name"], "Category 1")
        self.assertEqual(DEFAULT_CATEGORIES[0]["color"], "#005fa3")

        cats = load_categories()
        self.assertGreaterEqual(len(cats), 1)
        for c in cats:
            self.assertIn("id", c)
            self.assertIn("name", c)
            self.assertIn("color", c)

    def test_task_crud_and_reorder(self):
        task1 = add_task("[TEST] Task One", "Category 1")
        self.assertIsNotNone(task1)
        self.assertEqual(task1["text"], "[TEST] Task One")
        self.assertEqual(task1["category"], "Category 1")
        self.assertFalse(task1["completed"])
        self.assertEqual(task1["status"], "active")

        task2 = add_task("[TEST] Task Two", "Category 1")
        self.assertGreater(task2["display_order"], task1["display_order"])

        # Mark complete
        updated = update_task(task1["id"], completed=True)
        self.assertTrue(updated["completed"])
        self.assertIsNotNone(updated["completed_at"])

        # Reorder
        reorder_tasks([
            {"id": task2["id"], "display_order": 1, "category": "Category 1"},
            {"id": task1["id"], "display_order": 2, "category": "Category 1"}
        ])
        tasks = [t for t in get_tasks(status="active", category="Category 1") if t["text"].startswith("[TEST]")]
        self.assertEqual(tasks[0]["id"], task2["id"])
        self.assertEqual(tasks[1]["id"], task1["id"])

        # Update display_order directly
        updated_ord = update_task(task1["id"], display_order=50)
        self.assertEqual(updated_ord["display_order"], 50)

        # Delete
        self.assertTrue(delete_task(task2["id"]))
        self.assertTrue(delete_task(task1["id"]))

    def test_manual_archive_and_restore(self):
        task = add_task("[TEST] To Archive", "Category 2")
        update_task(task["id"], completed=True)

        count = archive_completed_now()
        self.assertGreaterEqual(count, 1)

        archived_tasks = [t for t in get_tasks(status="archived", category="Category 2") if t["id"] == task["id"]]
        self.assertEqual(len(archived_tasks), 1)
        self.assertEqual(archived_tasks[0]["status"], "archived")

        # Restore
        restored = restore_task(task["id"])
        self.assertEqual(restored["status"], "active")
        self.assertFalse(restored["completed"])

    def test_manual_archive_completed(self):
        # Create completed task
        task = add_task("[TEST] Manual Archive Task", "Category 3")
        update_task(task["id"], completed=True)

        # Run manual archive
        count = archive_completed_now()
        self.assertGreaterEqual(count, 1)

        # Check statuses
        archived_ids = [t["id"] for t in get_tasks(status="archived", category="Category 3")]
        self.assertIn(task["id"], archived_ids)

    def test_flask_routes(self):
        client = app.test_client()
        # Test categories endpoint
        res = client.get("/api/todo/categories")
        # May require auth or allow
        # If check_auth returns 401 without auth header, supply basic auth
        auth_headers = {}
        if res.status_code == 401:
            from index.index import get_auth_credentials
            import base64
            u, p = get_auth_credentials()
            if u and p:
                token = base64.b64encode(f"{u}:{p}".encode()).decode()
                auth_headers = {"Authorization": f"Basic {token}"}
                res = client.get("/api/todo/categories", headers=auth_headers)

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("categories", data)
        target_cat = data["categories"][0]["name"]

        # Test category status update endpoint
        res_cat_status = client.patch(
            "/api/todo/categories/status",
            json={"category": target_cat, "status": "In Progress [TEST]"},
            headers=auth_headers
        )
        self.assertEqual(res_cat_status.status_code, 200)
        cat_data = res_cat_status.get_json()
        self.assertTrue(cat_data.get("success"))
        self.assertEqual(cat_data.get("category", {}).get("custom_status"), "In Progress [TEST]")
        self.assertEqual(cat_data.get("category", {}).get("status"), "active")

        # Test items endpoint
        res_items = client.get("/api/todo/items?status=active", headers=auth_headers)
        self.assertEqual(res_items.status_code, 200)
        data_items = res_items.get_json()
        self.assertIn("tasks", data_items)

        # Test page render
        res_page = client.get("/todo", headers=auth_headers)
        self.assertEqual(res_page.status_code, 200)
        self.assertIn(b"To-Do Board", res_page.data)

    def test_task_created_above_completed_tasks(self):
        """Validates that newly added tasks are always placed above existing completed tasks."""
        # Add first task and mark it complete
        task_done = add_task("[TEST] Already Completed", "Category 1")
        update_task(task_done["id"], completed=True)

        # Add a new active task
        task_new = add_task("[TEST] Newly Added Active Task", "Category 1")

        # Fetch active tasks in category
        active_tasks = [t for t in get_tasks(status="active", category="Category 1") if t["text"].startswith("[TEST]")]
        active_ids = [t["id"] for t in active_tasks]

        self.assertIn(task_new["id"], active_ids)
        self.assertIn(task_done["id"], active_ids)

        # task_new must appear BEFORE task_done
        new_idx = active_ids.index(task_new["id"])
        done_idx = active_ids.index(task_done["id"])
        self.assertLess(new_idx, done_idx, "New active task must appear above completed task in display order")

    def test_category_status_management(self):
        """Validates setting and retrieving category status."""
        cat = add_category("[TEST] Status Test Cat", "#6366f1")
        self.assertEqual(cat["status"], "active")
        self.assertEqual(cat["custom_status"], "")

        updated = set_category_status("[TEST] Status Test Cat", "Reviewing PRs [TEST]")
        self.assertEqual(updated["custom_status"], "Reviewing PRs [TEST]")
        self.assertEqual(updated["status"], "active")

        cats = get_categories_with_status()
        found = next((c for c in cats if c["name"] == "[TEST] Status Test Cat"), None)
        self.assertIsNotNone(found)
        self.assertEqual(found["custom_status"], "Reviewing PRs [TEST]")

    def test_category_sqlite_crud_and_cascade(self):
        """Validates category creation, uniqueness constraints, updates, and cascading task renames."""
        # Add new category
        cat = add_category("[TEST] Infrastructure", "#10b981")
        self.assertIsNotNone(cat)
        self.assertEqual(cat["name"], "[TEST] Infrastructure")
        self.assertEqual(cat["color"], "#10b981")
        self.assertEqual(cat["status"], "active")
        self.assertEqual(cat["custom_status"], "")
        self.assertGreaterEqual(cat["display_order"], 1)

        # Disallow duplicate category name (case-insensitive)
        with self.assertRaises(ValueError):
            add_category("[test] infrastructure", "#f59e0b")

        # Disallow empty category name
        with self.assertRaises(ValueError):
            add_category("   ", "#f59e0b")

        # Fetch by id and by name
        fetched_id = get_category_by_id(cat["id"])
        self.assertEqual(fetched_id["name"], "[TEST] Infrastructure")
        fetched_name = get_category_by_name("[TEST] infrastructure")
        self.assertEqual(fetched_name["id"], cat["id"])

        # Add a task under this category
        task = add_task("[TEST] Setup Terraform", "[TEST] Infrastructure")
        self.assertEqual(task["category"], "[TEST] Infrastructure")

        # Update category name & color & custom_status, verify cascade to task
        updated_cat = update_category(cat["id"], name="[TEST] DevOps Infra", color="#6366f1", custom_status="In Review")
        self.assertEqual(updated_cat["name"], "[TEST] DevOps Infra")
        self.assertEqual(updated_cat["color"], "#6366f1")
        self.assertEqual(updated_cat["custom_status"], "In Review")
        self.assertEqual(updated_cat["status"], "active")

        # Check task category cascaded
        tasks = [t for t in get_tasks(category="[TEST] DevOps Infra") if t["id"] == task["id"]]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["category"], "[TEST] DevOps Infra")

        # Delete category
        self.assertTrue(delete_category(cat["id"]))
        self.assertIsNone(get_category_by_id(cat["id"]))

    def test_category_api_routes(self):
        """Validates POST /api/todo/categories and PATCH /api/todo/categories/<id> endpoints."""
        client = app.test_client()
        from index.index import get_auth_credentials
        import base64
        u, p = get_auth_credentials()
        auth_headers = {}
        if u and p:
            token = base64.b64encode(f"{u}:{p}".encode()).decode()
            auth_headers = {"Authorization": f"Basic {token}"}

        # POST /api/todo/categories with valid data
        res = client.post(
            "/api/todo/categories",
            json={"name": "[TEST] Backend API", "color": "#8b5cf6"},
            headers=auth_headers
        )
        self.assertEqual(res.status_code, 201)
        created_cat = res.get_json().get("category", {})
        self.assertEqual(created_cat.get("name"), "[TEST] Backend API")
        self.assertEqual(created_cat.get("color"), "#8b5cf6")
        cat_id = created_cat.get("id")

        # Duplicate name of active category returns 400
        res_dup = client.post(
            "/api/todo/categories",
            json={"name": "[TEST] backend api", "color": "#8b5cf6"},
            headers=auth_headers
        )
        self.assertEqual(res_dup.status_code, 400)

        # Empty name returns 400
        res_empty = client.post(
            "/api/todo/categories",
            json={"name": "", "color": "#8b5cf6"},
            headers=auth_headers
        )
        self.assertEqual(res_empty.status_code, 400)

        # Invalid color format returns 400
        res_bad_color = client.post(
            "/api/todo/categories",
            json={"name": "[TEST] Bad Color", "color": "blue"},
            headers=auth_headers
        )
        self.assertEqual(res_bad_color.status_code, 400)

        # PATCH /api/todo/categories/<id>
        res_patch = client.patch(
            f"/api/todo/categories/{cat_id}",
            json={"name": "[TEST] Core Backend", "custom_status": "Testing Patch"},
            headers=auth_headers
        )
        self.assertEqual(res_patch.status_code, 200)
        self.assertEqual(res_patch.get_json().get("category", {}).get("name"), "[TEST] Core Backend")
        self.assertEqual(res_patch.get_json().get("category", {}).get("custom_status"), "Testing Patch")

        # GET /api/todo/categories contains updated category
        res_get = client.get("/api/todo/categories", headers=auth_headers)
        self.assertEqual(res_get.status_code, 200)
        names = [c["name"] for c in res_get.get_json().get("categories", [])]
        self.assertIn("[TEST] Core Backend", names)

    def test_category_archival_and_cascade(self):
        """Validates category archival cascades to active tasks and filters appropriately on archive view."""
        client = app.test_client()
        from index.index import get_auth_credentials
        import base64
        u, p = get_auth_credentials()
        auth_headers = {}
        if u and p:
            token = base64.b64encode(f"{u}:{p}".encode()).decode()
            auth_headers = {"Authorization": f"Basic {token}"}

        # Create category and tasks
        cat = add_category("[TEST] Marketing Sprint", "#ec4899")
        t1 = add_task("[TEST] Launch campaign", "[TEST] Marketing Sprint")
        t2 = add_task("[TEST] Write blog post", "[TEST] Marketing Sprint")

        # Archive category via API
        res_archive = client.post(f"/api/todo/categories/{cat['id']}/archive", headers=auth_headers)
        self.assertEqual(res_archive.status_code, 200)
        data = res_archive.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("tasks_archived"), 2)
        self.assertEqual(data.get("category", {}).get("status"), "archived")

        # Active board GET /api/todo/items?status=active does NOT include archived category
        res_active = client.get("/api/todo/items?status=active", headers=auth_headers)
        active_cats = [c["name"] for c in res_active.get_json().get("categories", [])]
        self.assertNotIn("[TEST] Marketing Sprint", active_cats)

        # Archive board GET /api/todo/items?status=archived only shows active categories
        res_archived_view = client.get("/api/todo/items?status=archived", headers=auth_headers)
        archived_view_cats = [c["name"] for c in res_archived_view.get_json().get("categories", [])]
        self.assertNotIn("[TEST] Marketing Sprint", archived_view_cats)

        # GET /api/todo/categories/archived-summary includes archived category and its tasks
        res_summary = client.get("/api/todo/categories/archived-summary", headers=auth_headers)
        self.assertEqual(res_summary.status_code, 200)
        summary_cats = res_summary.get_json().get("archived_categories", [])
        mkt_cat = next((c for c in summary_cats if c["name"] == "[TEST] Marketing Sprint"), None)
        self.assertIsNotNone(mkt_cat)
        self.assertEqual(len(mkt_cat.get("tasks", [])), 2)

    def test_category_duplicate_conflict_and_restoration(self):
        """Validates 409 conflict when creating category with name of archived category, and restoration behavior."""
        client = app.test_client()
        from index.index import get_auth_credentials
        import base64
        u, p = get_auth_credentials()
        auth_headers = {}
        if u and p:
            token = base64.b64encode(f"{u}:{p}".encode()).decode()
            auth_headers = {"Authorization": f"Basic {token}"}

        # Create category and task, then archive it
        cat = add_category("[TEST] Analytics Q1", "#06b6d4")
        t = add_task("[TEST] Build Dashboard", "[TEST] Analytics Q1")
        archive_category(cat["id"])

        # Attempting to create category with same name returns 409 Conflict
        res_conflict = client.post(
            "/api/todo/categories",
            json={"name": "[TEST] Analytics Q1", "color": "#10b981"},
            headers=auth_headers
        )
        self.assertEqual(res_conflict.status_code, 409)
        conflict_data = res_conflict.get_json()
        self.assertEqual(conflict_data.get("conflict"), "archived")
        self.assertEqual(conflict_data.get("category", {}).get("id"), cat["id"])

        # Restore the archived category
        res_restore = client.post(
            f"/api/todo/categories/{cat['id']}/restore",
            json={"color": "#10b981"},
            headers=auth_headers
        )
        self.assertEqual(res_restore.status_code, 200)
        restored_cat = res_restore.get_json().get("category", {})
        self.assertEqual(restored_cat.get("status"), "active")
        self.assertEqual(restored_cat.get("color"), "#10b981")

        # Crucial check: Historical tasks remain archived!
        active_items = client.get("/api/todo/items?status=active", headers=auth_headers).get_json()
        mkt_active_tasks = [task for task in active_items.get("tasks", []) if task["category"] == "[TEST] Analytics Q1"]
        self.assertEqual(len(mkt_active_tasks), 0)

        # The restored category now appears on the Archive View with its historical tasks!
        archived_items = client.get("/api/todo/items?status=archived", headers=auth_headers).get_json()
        archived_cat_names = [c["name"] for c in archived_items.get("categories", [])]
        self.assertIn("[TEST] Analytics Q1", archived_cat_names)
        mkt_archived_tasks = [task for task in archived_items.get("tasks", []) if task["category"] == "[TEST] Analytics Q1"]
        self.assertEqual(len(mkt_archived_tasks), 1)
        self.assertEqual(mkt_archived_tasks[0]["text"], "[TEST] Build Dashboard")

    def test_openapi_spec(self):
        client = app.test_client()
        from index.index import get_auth_credentials
        import base64
        u, p = get_auth_credentials()
        auth_headers = {}
        if u and p:
            token = base64.b64encode(f"{u}:{p}".encode()).decode()
            auth_headers = {"Authorization": f"Basic {token}"}

        res = client.get("/openapi.json", headers=auth_headers)
        self.assertEqual(res.status_code, 200)
        spec = res.get_json()
        tag_names = [t["name"] for t in spec.get("tags", [])]
        self.assertIn("To Do", tag_names)
        self.assertIn("/api/todo/items", spec.get("paths", {}))
        self.assertIn("/api/todo/categories", spec.get("paths", {}))
        self.assertIn("/api/todo/categories/status", spec.get("paths", {}))
        self.assertIn("/api/todo/categories/{category_id}/archive", spec.get("paths", {}))
        self.assertIn("/api/todo/categories/{category_id}/restore", spec.get("paths", {}))
        self.assertIn("/api/todo/categories/archived-summary", spec.get("paths", {}))


    def test_task_day_tags(self):
        client = app.test_client()
        from index.index import get_auth_credentials
        import base64
        u, p = get_auth_credentials()
        auth_headers = {}
        if u and p:
            token = base64.b64encode(f"{u}:{p}".encode()).decode()
            auth_headers = {"Authorization": f"Basic {token}"}

        # Create task with day tag
        res = client.post(
            "/api/todo/items",
            json={"text": "[TEST] Monday Task", "category": "Category 1", "day_tag": "Monday"},
            headers=auth_headers
        )
        self.assertEqual(res.status_code, 201)
        task = res.get_json().get("task", {})
        self.assertEqual(task.get("day_tag"), "Monday")
        task_id = task.get("id")

        # Update day tag to Wednesday
        res_patch = client.patch(
            f"/api/todo/items/{task_id}",
            json={"day_tag": "Wednesday"},
            headers=auth_headers
        )
        self.assertEqual(res_patch.status_code, 200)
        updated_task = res_patch.get_json().get("task", {})
        self.assertEqual(updated_task.get("day_tag"), "Wednesday")

        # Fetch items and verify day_tag is returned
        res_get = client.get("/api/todo/items?status=active", headers=auth_headers)
        self.assertEqual(res_get.status_code, 200)
        items_data = res_get.get_json()
        target = next((t for t in items_data.get("tasks", []) if t["id"] == task_id), None)
        self.assertIsNotNone(target)
        self.assertEqual(target.get("day_tag"), "Wednesday")

        # Clear day tag
        res_clear = client.patch(
            f"/api/todo/items/{task_id}",
            json={"day_tag": ""},
            headers=auth_headers
        )
        self.assertEqual(res_clear.status_code, 200)
        self.assertEqual(res_clear.get_json().get("task", {}).get("day_tag"), "")

    def test_task_size_tags(self):
        client = app.test_client()
        from index.index import get_auth_credentials
        import base64
        u, p = get_auth_credentials()
        auth_headers = {}
        if u and p:
            token = base64.b64encode(f"{u}:{p}".encode()).decode()
            auth_headers = {"Authorization": f"Basic {token}"}

        # Create task with size tag and day tag
        res = client.post(
            "/api/todo/items",
            json={
                "text": "[TEST] Sized Task",
                "category": "Category 1",
                "day_tag": "Tuesday",
                "size_tag": "Small"
            },
            headers=auth_headers
        )
        self.assertEqual(res.status_code, 201)
        task = res.get_json().get("task", {})
        self.assertEqual(task.get("day_tag"), "Tuesday")
        self.assertEqual(task.get("size_tag"), "Small")
        task_id = task.get("id")

        # Update size tag to Medium
        res_patch_med = client.patch(
            f"/api/todo/items/{task_id}",
            json={"size_tag": "Medium"},
            headers=auth_headers
        )
        self.assertEqual(res_patch_med.status_code, 200)
        self.assertEqual(res_patch_med.get_json().get("task", {}).get("size_tag"), "Medium")
        # Day tag remains intact
        self.assertEqual(res_patch_med.get_json().get("task", {}).get("day_tag"), "Tuesday")

        # Update size tag to Long
        res_patch_long = client.patch(
            f"/api/todo/items/{task_id}",
            json={"size_tag": "Long"},
            headers=auth_headers
        )
        self.assertEqual(res_patch_long.status_code, 200)
        self.assertEqual(res_patch_long.get_json().get("task", {}).get("size_tag"), "Long")

        # Fetch active board tasks and verify size_tag is preserved
        res_get = client.get("/api/todo/items?status=active", headers=auth_headers)
        self.assertEqual(res_get.status_code, 200)
        items = res_get.get_json().get("tasks", [])
        target = next((t for t in items if t["id"] == task_id), None)
        self.assertIsNotNone(target)
        self.assertEqual(target.get("size_tag"), "Long")
        self.assertEqual(target.get("day_tag"), "Tuesday")

        # Clear both tags
        res_clear = client.patch(
            f"/api/todo/items/{task_id}",
            json={"day_tag": "", "size_tag": ""},
            headers=auth_headers
        )
        self.assertEqual(res_clear.status_code, 200)
        cleared_task = res_clear.get_json().get("task", {})
        self.assertEqual(cleared_task.get("day_tag"), "")
        self.assertEqual(cleared_task.get("size_tag"), "")


if __name__ == "__main__":
    unittest.main()

