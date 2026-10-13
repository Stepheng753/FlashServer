import os
import pytz

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "tasks.db")

APP_TIMEZONE = pytz.timezone("America/Los_Angeles")

DEFAULT_CATEGORIES = [
    {"name": "Category 1", "color": "#005fa3"},
    {"name": "Category 2", "color": "#55b080"},
    {"name": "Category 3", "color": "#a479b1"},
    {"name": "Category 4", "color": "#e7ba51"},
    {"name": "Category 5", "color": "#bc2b2e"},
    {"name": "Category 6", "color": "#f294e9"},
    {"name": "Category 7", "color": "#e0963c"}
]


def save_category_status(category_name, status_text):
    """Updates the status field of a category in SQLite."""
    try:
        from .db import set_category_status
        return set_category_status(category_name, status_text)
    except Exception as e:
        print(f"[ToDo] Note: could not set category status: {e}")
        return None


def load_categories(status="active"):
    """
    Loads categories from SQLite categories table.
    Falls back to DEFAULT_CATEGORIES if the DB table is not yet initialized.
    """
    try:
        from .db import get_categories
        cats = get_categories(status=status)
        if cats:
            return cats
    except Exception as e:
        print(f"[ToDo] Note loading categories from DB: {e}")

    return [
        {"id": c["name"], "name": c["name"], "color": c["color"], "status": "active", "custom_status": "", "status_text": ""}
        for c in DEFAULT_CATEGORIES
    ]
