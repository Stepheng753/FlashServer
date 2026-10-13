import json
import os
import pytz

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
TUTORING_DIR = os.path.dirname(os.path.abspath(__file__))

PST = pytz.timezone('America/Los_Angeles')


def load_json_file(filename):
    for folder in [CONFIG_DIR, BASE_DIR]:
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
    return {}


def get_config():
    return load_json_file('config.json')


def get_secrets():
    return load_json_file('secrets.json')


def __getattr__(name):
    cfg = get_config()
    sec = get_secrets()
    if name == 'CONFIG':
        return cfg
    if name == 'SECRETS':
        return sec
    if name == 'GOOGLE_CALENDAR_ID':
        return cfg.get('GOOGLE_CALENDAR_ID')
    if name == 'PAY_PARENT_FOLDER_ID':
        return cfg.get('PAY_PARENT_FOLDER_ID')
    if name == 'TEMPLATE_SHEET_ID':
        return cfg.get('TEMPLATE_SHEET_ID')
    if name == 'NOTIFICATION_EMAIL':
        return cfg.get('NOTIFICATION_EMAIL')
    if name == 'APP_HOST':
        return cfg.get('APP_HOST')
    if name == 'OAUTH_FILE':
        oauth_filename = cfg.get('OAUTH_FILE')
        if not oauth_filename:
            return None
        for folder in [CONFIG_DIR, BASE_DIR]:
            p = os.path.join(folder, oauth_filename)
            if os.path.exists(p):
                return p
        return os.path.join(CONFIG_DIR, oauth_filename)
    if name == 'KEYS_DIR':
        d = os.path.join(TUTORING_DIR, 'keys')
        os.makedirs(d, exist_ok=True)
        return d
    if name == 'TOKEN_PICKLE_FILE':
        return os.path.join(TUTORING_DIR, 'keys', 'token.pickle')
    if name == 'TWILIO_ACCOUNT_SID':
        return cfg.get('TWILIO_ACCOUNT_SID')
    if name == 'TWILIO_API_KEY_SID':
        return cfg.get('TWILIO_API_KEY_SID')
    if name == 'TWILIO_API_SECRET':
        return sec.get('TWILIO_API_SECRET')
    if name == 'TWILIO_FROM_NUMBER':
        return cfg.get('TWILIO_FROM_NUMBER')
    if name == 'LOGS_DIR':
        d = os.path.join(TUTORING_DIR, 'logs')
        os.makedirs(d, exist_ok=True)
        return d
    if name == 'TEXT_LOG_FILE':
        return os.path.join(TUTORING_DIR, 'logs', 'text_messages.log')
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

