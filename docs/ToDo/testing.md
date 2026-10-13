# ToDo Testing

Tests: [modules/ToDo/tests/](../../modules/ToDo/tests/)

```bash
.venv/bin/python -m unittest discover -s modules/ToDo/tests -p "test_*.py"
```

## `test_todo.py` (real database)

Runs against the real `data/tasks.db` through the real Flask app (credentials from `config/secrets.json`). Each test creates rows whose text or name starts with `[TEST]`, and `setUp` / `tearDown` delete every `[TEST]` row. Do not name real tasks `[TEST]...`.

Covers the default categories, task CRUD and reorder, new tasks placed above completed ones, day and size tags, manual archive and restore, category CRUD, archive cascade, duplicate and archived-conflict restoration, and the OpenAPI listing.

## `test_todo_isolated.py` (temporary database)

Patches `modules.ToDo.db.DB_PATH` to a temporary file, so it never touches `data/tasks.db`. Routes are tested through a Flask app that only registers `todo_bp`.

| Class | What it checks |
| :--- | :--- |
| `TestSeedingAndMigration` | Default categories seeded once. A database from before the tag columns is migrated. |
| `TestTaskRules` | Empty text rejected, default category, completion timestamps and sinking completed tasks, update validation, reorder across categories, scoped archive-all, restore ordering, scoped delete-all. |
| `TestCategoryRules` | Hex color validation, duplicate names and invalid status rejected, archive marks tasks completed, restore keeps tasks archived, archived-name conflict, ordering, status text. |
| `TestLoadCategories` | Reads the database, falls back to defaults when it fails, `save_category_status` swallows errors. |
| `TestTodoRoutes` | Page renders and has no rollover badge. Every endpoint: items CRUD with `PATCH` and `PUT`, archive and restore flow, archived view, reorder, category lifecycle with the 400 / 404 / 409 cases, and all three category-status routes. |
