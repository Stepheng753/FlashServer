import base64
import json
import os
from flask import request, make_response

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")


def get_auth_credentials():
    username = None
    password = None

    for folder in [CONFIG_DIR, BASE_DIR]:
        secrets_path = os.path.join(folder, "secrets.json")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r") as f:
                    sec = json.load(f)
                    username = sec.get("USERNAME")
                    password = sec.get("PASSWORD")
                    if username and password:
                        break
            except Exception:
                pass

    if not username:
        for folder in [CONFIG_DIR, BASE_DIR]:
            config_path = os.path.join(folder, "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r") as f:
                        cfg = json.load(f)
                        username = cfg.get("USERNAME")
                        if username:
                            break
                except Exception:
                    pass

    return username, password


def check_auth():
    # Only allow OAuth callback to complete if external redirect occurs
    # All Swagger docs (/ and /docs and /openapi.json) are strictly password protected
    if request.path in ['/login_oauth', '/TutoringCalculator/login_oauth'] and 'code' in request.args:
        return None

    # Allow static assets, CSS, and favicon without triggering separate auth prompt
    if request.path.startswith('/static/') or request.path == '/favicon.ico':
        return None

    # Allow public access to the Privacy Policy for Google OAuth app publishing and direct link access
    if request.path.rstrip('/') in ['/privacy', '/TutoringCalculator/privacy']:
        return None

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Basic '):
        return make_response('Could not verify!', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

    auth_bytes = auth_header.split(' ')[1].encode('ascii')
    try:
        decoded_bytes = base64.b64decode(auth_bytes)
        decoded_string = decoded_bytes.decode('ascii')
        username, password = decoded_string.split(':', 1)
    except (base64.binascii.Error, ValueError):
        return make_response('Invalid authorization header.', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

    valid_user, valid_pass = get_auth_credentials()
    if not valid_user or not valid_pass:
        return make_response(
            "Authentication credentials not configured on server (secrets.json / config.json missing).",
            500,
            {'Content-Type': 'text/plain'}
        )

    if not username or username.lower() != valid_user.lower() or password != valid_pass:
        return make_response('Could not verify!', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

    return None
