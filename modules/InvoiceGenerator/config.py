import os
import pytz

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "invoices.db")

APP_TIMEZONE = pytz.timezone("America/Los_Angeles")

DEFAULT_CURRENCY = "$"
DEFAULT_DUE_DAYS = 14

DEFAULT_SENDER = {
    "name": "Stephen Giang",
    "email": "stepheng753@gmail.com",
    "phone": "",
    "address": "",
    "website": "",
    "payment_instructions": "Zelle: stepheng753@gmail.com\nVenmo: @Stephen-Giang",
    "default_notes": "Thank you for your business! Please remit payment within the specified due date.",
    "is_default": 1
}
