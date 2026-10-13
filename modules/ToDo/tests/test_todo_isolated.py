"""ToDo tests that run against a throwaway SQLite file, never data/tasks.db."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

# Add repo root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.ToDo import config as todo_config
from modules.ToDo import db as todo_db
from modules.ToDo.routes import todo_bp


class TodoDbTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(todo_db, "DB_PATH", os.path.join(self.tmp.name, "tasks_test.db"))
        self.patch.start()
        todo_db.init_db()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def names(self, tasks):
        return [t["text"] for t in tasks]


class TestSeedingAndMigration(TodoDbTestCase):

    def test_default_categories_are_seeded_once(self):
        cats = todo_db.get_categories()
        self.assertEqual([c["name"] for c in cats], [c["name"] for c in todo_config.DEFAULT_CATEGORIES])
        todo_db.init_db()
        self.assertEqual(len(todo_db.get_categories()), len(todo_config.DEFAULT_CATEGORIES))

    def test_old_tasks_table_is_migrated_with_tag_columns(self):
        import sqlite3
        path = os.path.join(self.tmp.name, "legacy.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, text TEXT NOT NULL, "
                     "completed INTEGER DEFAULT 0, completed_at TEXT, status TEXT DEFAULT 'active', "
                     "display_order INTEGER DEFAULT 0, archived_at TEXT, created_at TEXT NOT NULL)")
        conn.execute("INSERT INTO tasks (category, text, created_at) VALUES ('Old', 'legacy task', 'x')")
        conn.commit()
        conn.close()
        with patch.object(todo_db, "DB_PATH", path):
            todo_db.init_db()
            task = todo_db.get_tasks()[0]
        self.assertEqual((task["text"], task["day_tag"], task["size_tag"]), ("legacy task", "", ""))


class TestTaskRules(TodoDbTestCase):

    def test_empty_text_rejected_and_defaults_applied(self):
        with self.assertRaises(ValueError):
            todo_db.add_task("   ", "Category 1")
        task = todo_db.add_task("  trimmed  ", "")
        self.assertEqual((task["text"], task["category"]), ("trimmed", "Misc"))

    def test_completion_sets_and_clears_timestamp_and_sinks_task(self):
        a = todo_db.add_task("a", "Category 1")
        b = todo_db.add_task("b", "Category 1")
        done = todo_db.update_task(a["id"], completed=True)
        self.assertTrue(done["completed"])
        self.assertIsNotNone(done["completed_at"])
        self.assertEqual(self.names(todo_db.get_tasks(category="Category 1")), ["b", "a"])
        undone = todo_db.update_task(a["id"], completed=False)
        self.assertIsNone(undone["completed_at"])

    def test_update_validation_and_noop(self):
        task = todo_db.add_task("a", "Category 1")
        with self.assertRaises(ValueError):
            todo_db.update_task(task["id"], text="  ")
        self.assertEqual(todo_db.update_task(task["id"])["text"], "a")
        self.assertIsNone(todo_db.update_task(9999, text="x"))

    def test_reorder_can_move_between_categories(self):
        a = todo_db.add_task("a", "Category 1")
        b = todo_db.add_task("b", "Category 1")
        todo_db.reorder_tasks([{"id": a["id"], "display_order": 2}, {"id": b["id"], "display_order": 1, "category": "Category 2"}])
        self.assertEqual(self.names(todo_db.get_tasks(category="Category 2")), ["b"])
        self.assertEqual(self.names(todo_db.get_tasks(category="Category 1")), ["a"])

    def test_archive_all_scoped_to_category(self):
        todo_db.add_task("a", "Category 1")
        todo_db.add_task("b", "Category 2")
        self.assertEqual(todo_db.archive_all(category="Category 1"), 1)
        self.assertEqual(self.names(todo_db.get_tasks("archived")), ["a"])
        self.assertEqual(self.names(todo_db.get_tasks("active")), ["b"])

    def test_restore_returns_task_uncompleted_above_completed(self):
        keep = todo_db.add_task("keep", "Category 1")
        todo_db.update_task(keep["id"], completed=True)
        old = todo_db.add_task("old", "Category 1")
        todo_db.update_task(old["id"], completed=True)
        todo_db.archive_completed_now()
        again = todo_db.add_task("again", "Category 1")
        restored = todo_db.restore_task(old["id"])
        self.assertFalse(restored["completed"])
        self.assertEqual(restored["status"], "active")
        self.assertEqual(self.names(todo_db.get_tasks(category="Category 1")), ["again", "old"])
        self.assertIsNone(todo_db.restore_task(9999))

    def test_delete_all_filters_by_status_and_category(self):
        todo_db.add_task("a", "Category 1")
        todo_db.add_task("b", "Category 2")
        done = todo_db.add_task("c", "Category 2")
        todo_db.update_task(done["id"], completed=True)
        todo_db.archive_completed_now()
        self.assertEqual(todo_db.delete_all(status="active", category="Category 1"), 1)
        self.assertEqual(todo_db.delete_all(status="archived"), 1)
        self.assertEqual(self.names(todo_db.get_tasks()), ["b"])


class TestCategoryRules(TodoDbTestCase):

    def test_color_validation_and_normalization(self):
        cat = todo_db.add_category("Ops", "10b981")
        self.assertEqual(cat["color"], "#10b981")
        with self.assertRaises(ValueError):
            todo_db.add_category("Bad", "#12")
        with self.assertRaises(ValueError):
            todo_db.update_category(cat["id"], color="zzzzzz")

    def test_update_rejects_duplicate_name_and_bad_status(self):
        a = todo_db.add_category("Alpha")
        todo_db.add_category("Beta")
        with self.assertRaises(ValueError):
            todo_db.update_category(a["id"], name="beta")
        with self.assertRaises(ValueError):
            todo_db.update_category(a["id"], name="  ")
        with self.assertRaises(ValueError):
            todo_db.update_category(a["id"], status="paused")
        self.assertIsNone(todo_db.update_category(9999, name="x"))
        self.assertEqual(todo_db.update_category(a["id"], name="ALPHA")["name"], "ALPHA")  # case-only rename allowed

    def test_archive_marks_tasks_completed_and_restore_keeps_them_archived(self):
        cat = todo_db.add_category("Temp")
        todo_db.add_task("t1", "Temp")
        result = todo_db.archive_category(cat["id"])
        self.assertEqual(result["tasks_archived"], 1)
        archived = todo_db.get_archived_categories_with_tasks()
        self.assertEqual([(c["name"], c["task_count"]) for c in archived if c["name"] == "Temp"], [("Temp", 1)])
        self.assertTrue(archived[-1]["tasks"][0]["completed"])
        self.assertNotIn("Temp", [c["name"] for c in todo_db.get_categories()])

        todo_db.restore_category(cat["id"], color="#abcdef")
        restored = todo_db.get_category_by_id(cat["id"])
        self.assertEqual((restored["status"], restored["color"]), ("active", "#abcdef"))
        self.assertEqual(todo_db.get_tasks("active", category="Temp"), [])
        self.assertEqual(len(todo_db.get_tasks("archived", category="Temp")), 1)
        self.assertIsNone(todo_db.archive_category(9999))
        self.assertIsNone(todo_db.restore_category(9999))

    def test_archived_name_conflict_carries_category(self):
        cat = todo_db.add_category("Dup")
        todo_db.archive_category(cat["id"])
        with self.assertRaises(todo_db.CategoryArchivedConflict) as ctx:
            todo_db.add_category("dup")
        self.assertEqual(ctx.exception.category["id"], cat["id"])

    def test_new_categories_append_to_the_end(self):
        first = todo_db.add_category("Z1")
        second = todo_db.add_category("Z2")
        self.assertEqual(second["display_order"], first["display_order"] + 1)

    def test_set_status_is_case_insensitive_and_unknown_category_echoes(self):
        todo_db.set_category_status("category 1", "Blocked")
        self.assertEqual(todo_db.get_category_by_name("Category 1")["custom_status"], "Blocked")
        ghost = todo_db.set_category_status("Ghost", "x")
        self.assertEqual(ghost["status_text"], "x")


class TestLoadCategories(TodoDbTestCase):

    def test_reads_from_database(self):
        todo_db.add_category("Extra")
        with patch.object(todo_db, "DB_PATH", todo_db.DB_PATH):
            self.assertIn("Extra", [c["name"] for c in todo_config.load_categories()])

    def test_falls_back_to_defaults_when_db_fails(self):
        with patch("modules.ToDo.db.get_categories", side_effect=RuntimeError("down")):
            cats = todo_config.load_categories()
        self.assertEqual([c["name"] for c in cats], [c["name"] for c in todo_config.DEFAULT_CATEGORIES])

    def test_save_category_status_swallows_errors(self):
        with patch("modules.ToDo.db.set_category_status", side_effect=RuntimeError("down")):
            self.assertIsNone(todo_config.save_category_status("x", "y"))


class TestTodoRoutes(TodoDbTestCase):

    def setUp(self):
        super().setUp()
        app = Flask(__name__)
        app.register_blueprint(todo_bp)
        self.client = app.test_client()

    def test_page_renders(self):
        resp = self.client.get("/todo")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"<html", resp.data.lower())

    def test_page_has_no_scheduled_rollover_badge(self):
        self.assertNotIn(b"rollover", self.client.get("/todo").data.lower())

    def test_items_crud_and_validation(self):
        self.assertEqual(self.client.post("/api/todo/items", json={"text": " "}).status_code, 400)
        created = self.client.post("/api/todo/items", json={"text": "Write docs", "category": "Category 2", "day_tag": "Friday", "size_tag": "Small"})
        self.assertEqual(created.status_code, 201)
        task = created.get_json()["task"]
        self.assertEqual((task["day_tag"], task["size_tag"]), ("Friday", "Small"))

        for method in (self.client.patch, self.client.put):
            resp = method(f"/api/todo/items/{task['id']}", json={"text": "Updated"})
            self.assertEqual(resp.get_json()["task"]["text"], "Updated")
        self.assertEqual(self.client.patch(f"/api/todo/items/{task['id']}", json={"text": ""}).status_code, 400)
        self.assertEqual(self.client.patch("/api/todo/items/9999", json={"text": "x"}).status_code, 404)

        listed = self.client.get("/api/todo/items?status=bogus&category=Category 2").get_json()
        self.assertEqual(listed["status"], "active")
        self.assertEqual([t["text"] for t in listed["tasks"]], ["Updated"])

        self.assertEqual(self.client.delete(f"/api/todo/items/{task['id']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/todo/items/{task['id']}").status_code, 404)

    def test_archive_restore_and_delete_flow(self):
        ids = [self.client.post("/api/todo/items", json={"text": t, "category": "Category 1"}).get_json()["task"]["id"] for t in "abc"]
        self.client.patch(f"/api/todo/items/{ids[0]}", json={"completed": True})

        self.assertEqual(self.client.post("/api/todo/archive-completed").get_json()["archived_count"], 1)
        archived = self.client.get("/api/todo/items?status=archived").get_json()
        self.assertEqual([t["text"] for t in archived["tasks"]], ["a"])

        restored = self.client.post(f"/api/todo/items/{ids[0]}/restore")
        self.assertEqual(restored.get_json()["task"]["status"], "active")
        self.assertEqual(self.client.post("/api/todo/items/9999/restore").status_code, 404)

        self.assertEqual(self.client.post("/api/todo/archive-all", json={"category": "Category 1"}).get_json()["archived_count"], 3)
        self.assertEqual(self.client.post("/api/todo/delete-all", json={"status": "archived", "category": "Category 1"}).get_json()["deleted_count"], 3)
        self.assertEqual(self.client.post("/api/todo/delete-all", json={"status": "nonsense"}).get_json()["deleted_count"], 0)

    def test_archived_view_hides_tasks_of_archived_categories(self):
        cat = self.client.post("/api/todo/categories", json={"name": "Gone"}).get_json()["category"]
        self.client.post("/api/todo/items", json={"text": "hidden", "category": "Gone"})
        self.client.post(f"/api/todo/categories/{cat['id']}/archive")
        archived = self.client.get("/api/todo/items?status=archived").get_json()
        self.assertNotIn("hidden", [t["text"] for t in archived["tasks"]])

    def test_reorder_validation(self):
        self.assertEqual(self.client.post("/api/todo/reorder", json={"items": "nope"}).status_code, 400)
        a = self.client.post("/api/todo/items", json={"text": "a", "category": "Category 1"}).get_json()["task"]
        b = self.client.post("/api/todo/items", json={"text": "b", "category": "Category 1"}).get_json()["task"]
        resp = self.client.post("/api/todo/reorder", json={"items": [
            {"id": a["id"], "display_order": 2}, {"id": b["id"], "display_order": 1}]})
        self.assertTrue(resp.get_json()["success"])
        tasks = self.client.get("/api/todo/items?category=Category 1").get_json()["tasks"]
        self.assertEqual([t["text"] for t in tasks], ["b", "a"])

    def test_category_lifecycle(self):
        self.assertEqual(self.client.post("/api/todo/categories", json={"name": ""}).status_code, 400)
        created = self.client.post("/api/todo/categories", json={"name": "Side", "color": "#112233"})
        self.assertEqual(created.status_code, 201)
        cat = created.get_json()["category"]
        self.assertEqual(self.client.post("/api/todo/categories", json={"name": "side"}).status_code, 400)
        self.assertEqual(self.client.post("/api/todo/categories", json={"name": "x", "color": "nope"}).status_code, 400)

        resp = self.client.patch(f"/api/todo/categories/{cat['id']}", json={"name": "Side Quest", "color": "#445566"})
        self.assertEqual(resp.get_json()["category"]["name"], "Side Quest")
        self.assertEqual(self.client.put(f"/api/todo/categories/{cat['id']}", json={"status": "In review"}).get_json()["category"]["custom_status"], "In review")
        self.assertEqual(self.client.patch(f"/api/todo/categories/{cat['id']}", json={"color": "xyz1"}).status_code, 400)
        self.assertEqual(self.client.patch("/api/todo/categories/9999", json={"name": "x"}).status_code, 404)

        archived = self.client.post(f"/api/todo/categories/{cat['id']}/archive")
        self.assertTrue(archived.get_json()["success"])
        self.assertEqual(self.client.post("/api/todo/categories/9999/archive").status_code, 404)
        names = [c["name"] for c in self.client.get("/api/todo/categories").get_json()["categories"]]
        self.assertNotIn("Side Quest", names)
        summary = self.client.get("/api/todo/categories/archived-summary").get_json()["archived_categories"]
        self.assertEqual([c["name"] for c in summary], ["Side Quest"])

        conflict = self.client.post("/api/todo/categories", json={"name": "side quest"})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.get_json()["conflict"], "archived")

        restored = self.client.post(f"/api/todo/categories/{cat['id']}/restore", json={"color": "#aabbcc"})
        self.assertEqual(restored.get_json()["category"]["color"], "#aabbcc")
        self.assertEqual(self.client.post("/api/todo/categories/9999/restore").status_code, 404)

    def test_category_status_routes(self):
        for method in (self.client.patch, self.client.put, self.client.post):
            resp = method("/api/todo/categories/status", json={"category": "Category 1", "status": "Waiting"})
            self.assertEqual(resp.get_json()["category"]["custom_status"], "Waiting")
        self.assertEqual(self.client.patch("/api/todo/categories/status", json={"status": "x"}).status_code, 400)

        resp = self.client.post("/api/todo/categories/Category 2/status", json={"status": "Path form"})
        self.assertEqual(resp.get_json()["category"]["custom_status"], "Path form")


if __name__ == "__main__":
    unittest.main()
