import os
import pytz

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "finance.db")

APP_TIMEZONE = pytz.timezone("America/Los_Angeles")

SIMPLEFIN_CLAIM_BASE_URL = "https://beta-bridge.simplefin.org/simplefin/claim"
SIMPLEFIN_AUTH_KEY = "simplefin_access_url"
SIMPLEFIN_CLAIM_KEY = "simplefin_claim_token"
SIMPLEFIN_LAST_SYNC_KEY = "simplefin_last_sync"

SECRETS_FILE = os.path.join(CONFIG_DIR, "secrets.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def get_secret(key: str, default=None):
    """Fetches a secret key from secrets.json or config.json."""
    for path in [SECRETS_FILE, CONFIG_FILE]:
        if os.path.exists(path):
            try:
                import json
                with open(path, "r") as f:
                    data = json.load(f)
                    if key in data and data[key]:
                        return data[key]
            except Exception:
                pass
    return default


def save_secret(key: str, value: str):
    """Saves a secret key to secrets.json, creating or updating it."""
    import json
    data = {}
    if os.path.exists(SECRETS_FILE):
        try:
            with open(SECRETS_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}

    data[key] = value
    try:
        with open(SECRETS_FILE, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        return True
    except Exception as e:
        print(f"[Finance] Error saving secret {key}: {e}")
        return False

