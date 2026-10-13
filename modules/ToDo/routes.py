from flask import Blueprint, jsonify, render_template, request
from .config import load_categories
from .db import (
    init_db,
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
    get_categories_with_status,
    set_category_status,
    get_tasks,
    get_task_by_id,
    add_task,
    update_task,
    reorder_tasks,
    archive_completed_now,
    archive_all,
    restore_task,
    delete_task,
    delete_all
)

todo_bp = Blueprint('todo', __name__, template_folder='.')

# Ensure DB is initialized when routes are loaded
init_db()


@todo_bp.route("/todo")
def todo_page():
    """Renders the interactive To-Do grid application."""
    categories = get_categories(status="active")
    return render_template("todo.html", categories=categories)


@todo_bp.route("/api/todo/categories", methods=["GET"])
def api_get_categories():
    """Returns the list of categories with color codes and current status from SQLite."""
    status = request.args.get("status", "active")
    categories = get_categories(status=status)
    return jsonify({"categories": categories})


@todo_bp.route("/api/todo/categories", methods=["POST"])
def api_add_category():
    """Creates a new category with a name and color."""
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name", "").strip()
    color = data.get("color", "#5b95cb").strip()

    if not name:
        return jsonify({"error": "Category name is required."}), 400

    try:
        category = add_category(name=name, color=color)
        return jsonify({"success": True, "category": category}), 201
    except CategoryArchivedConflict as cac:
        return jsonify({
            "error": str(cac),
            "conflict": "archived",
            "category": cac.category
        }), 409
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todo_bp.route("/api/todo/categories/<int:category_id>", methods=["PATCH", "PUT"])
def api_update_category(category_id):
    """Updates category properties: name, color, status, custom_status, or display_order."""
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    color = data.get("color")
    raw_status = data.get("status")
    custom_status = data.get("custom_status")
    status = None
    if raw_status is not None:
        if raw_status.strip().lower() in ("active", "archived"):
            status = raw_status.strip().lower()
        else:
            if custom_status is None:
                custom_status = raw_status.strip()
    display_order = data.get("display_order")

    try:
        category = update_category(
            category_id,
            name=name,
            color=color,
            status=status,
            custom_status=custom_status,
            display_order=display_order
        )
        if not category:
            return jsonify({"error": "Category not found."}), 404
        return jsonify({"success": True, "category": category})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todo_bp.route("/api/todo/categories/<int:category_id>/archive", methods=["POST"])
def api_archive_category(category_id):
    """Archives a category and cascades to automatically archive its active tasks."""
    try:
        res = archive_category(category_id)
        if not res:
            return jsonify({"error": "Category not found."}), 404
        return jsonify({
            "success": True,
            "category": res["category"],
            "tasks_archived": res["tasks_archived"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todo_bp.route("/api/todo/categories/<int:category_id>/restore", methods=["POST"])
def api_restore_category(category_id):
    """Restores an archived category to active status without altering historical tasks."""
    data = request.get_json(force=True, silent=True) or {}
    color = data.get("color")
    try:
        category = restore_category(category_id, color=color)
        if not category:
            return jsonify({"error": "Category not found."}), 404
        return jsonify({"success": True, "category": category})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todo_bp.route("/api/todo/categories/archived-summary", methods=["GET"])
def api_archived_categories_summary():
    """Returns all archived categories with their archived tasks."""
    try:
        archived = get_archived_categories_with_tasks()
        return jsonify({"archived_categories": archived})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todo_bp.route("/api/todo/categories/status", methods=["PATCH", "PUT", "POST"])
def api_update_category_status():
    """Updates the status text for a specific category."""
    data = request.get_json(force=True, silent=True) or {}
    category = data.get("category", "").strip()
    status = data.get("status", "").strip()
    if not category:
        return jsonify({"error": "Category name is required."}), 400

    try:
        updated_cat = set_category_status(category=category, status=status)
        return jsonify({"success": True, "category": updated_cat})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todo_bp.route("/api/todo/categories/<path:category_name>/status", methods=["PATCH", "PUT", "POST"])
def api_update_category_status_path(category_name):
    """Updates the status text for a specific category via URL path."""
    data = request.get_json(force=True, silent=True) or {}
    status = data.get("status", "").strip()
    category_name = (category_name or "").strip()
    if not category_name:
        return jsonify({"error": "Category name is required."}), 400

    try:
        updated_cat = set_category_status(category=category_name, status=status)
        return jsonify({"success": True, "category": updated_cat})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todo_bp.route("/api/todo/items", methods=["GET"])
def api_get_items():
    """
    Returns tasks filtered by status ('active' or 'archived') and optional category.
    Only active categories and their tasks are returned for the main boards.
    """
    status = request.args.get("status", "active").lower()
    if status not in ["active", "archived"]:
        status = "active"
    category = request.args.get("category")

    active_categories = get_categories(status="active")
    tasks = get_tasks(status=status, category=category)

    if status == "archived":
        # Archive View must only show active categories and their archived tasks
        active_names = {c["name"] for c in active_categories}
        tasks = [t for t in tasks if t["category"] in active_names]

    return jsonify({
        "status": status,
        "categories": active_categories,
        "tasks": tasks
    })


@todo_bp.route("/api/todo/items", methods=["POST"])
def api_add_item():
    """Creates a new task in a category."""
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "").strip()
    category = data.get("category", "Category 1").strip()
    day_tag = data.get("day_tag", "").strip()
    size_tag = data.get("size_tag", "").strip()

    if not text:
        return jsonify({"error": "Task text is required."}), 400

    try:
        task = add_task(text=text, category=category, day_tag=day_tag, size_tag=size_tag)
        return jsonify({"success": True, "task": task}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todo_bp.route("/api/todo/items/<int:item_id>", methods=["PATCH", "PUT"])
def api_update_item(item_id):
    """Updates task properties: text, category, completion state, day tag, or size tag."""
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text")
    category = data.get("category")
    completed = data.get("completed")
    display_order = data.get("display_order")
    day_tag = data.get("day_tag")
    size_tag = data.get("size_tag")

    try:
        updated = update_task(
            item_id,
            text=text,
            category=category,
            completed=completed,
            display_order=display_order,
            day_tag=day_tag,
            size_tag=size_tag
        )
        if not updated:
            return jsonify({"error": "Task not found."}), 404
        return jsonify({"success": True, "task": updated})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@todo_bp.route("/api/todo/items/<int:item_id>", methods=["DELETE"])
def api_delete_item(item_id):
    """Permanently deletes a task."""
    deleted = delete_task(item_id)
    if not deleted:
        return jsonify({"error": "Task not found."}), 404
    return jsonify({"success": True, "id": item_id})


@todo_bp.route("/api/todo/items/<int:item_id>/restore", methods=["POST"])
def api_restore_item(item_id):
    """Restores an archived task back to the active list."""
    task = restore_task(item_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404
    return jsonify({"success": True, "task": task})


@todo_bp.route("/api/todo/reorder", methods=["POST"])
def api_reorder():
    """Updates display order and category assignment for a list of items."""
    data = request.get_json(force=True, silent=True) or {}
    items = data.get("items", [])
    if not isinstance(items, list):
        return jsonify({"error": "Items list expected."}), 400

    reorder_tasks(items)
    return jsonify({"success": True})


@todo_bp.route("/api/todo/archive-completed", methods=["POST"])
def api_archive_completed():
    """Immediately archives all crossed-out (completed) active tasks."""
    count = archive_completed_now()
    return jsonify({"success": True, "archived_count": count})


@todo_bp.route("/api/todo/archive-all", methods=["POST"])
def api_archive_all():
    """Archives all active tasks (or for a specified category)."""
    data = request.get_json(force=True, silent=True) or {}
    category = data.get("category")
    count = archive_all(category=category)
    return jsonify({"success": True, "archived_count": count})


@todo_bp.route("/api/todo/delete-all", methods=["POST"])
def api_delete_all():
    """Permanently deletes all tasks in the current status / category."""
    data = request.get_json(force=True, silent=True) or {}
    status = data.get("status", "active").lower()
    category = data.get("category")
    if status not in ["active", "archived"]:
        status = "active"

    count = delete_all(status=status, category=category)
    return jsonify({"success": True, "deleted_count": count})
