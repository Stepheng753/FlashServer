import os
import pickle

# Allow local HTTP for OAuth callbacks
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import request, redirect, url_for
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from ..config import OAUTH_FILE, TOKEN_PICKLE_FILE, APP_HOST

SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.send'
]


def get_credentials():
    """Gets valid user credentials from storage or automatically refreshes them."""
    creds = None
    if os.path.exists(TOKEN_PICKLE_FILE):
        try:
            with open(TOKEN_PICKLE_FILE, 'rb') as token_file:
                creds = pickle.load(token_file)
        except Exception as e:
            print(f"Error loading token.pickle: {e}")
            creds = None

    if creds:
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(TOKEN_PICKLE_FILE, 'wb') as token_file:
                        pickle.dump(creds, token_file)
                    print("Google OAuth token refreshed successfully.")
                except RefreshError as e:
                    print(f"Token refresh failed: {e}")
                    creds = None
            else:
                creds = None

    return creds


def get_redirect_uri():
    """Determines the appropriate redirect URI matching OAuth configuration."""
    host = request.host.lower() if request.host else ""
    if 'dev.stepheng753.com' in host:
        return 'https://dev.stepheng753.com/TutoringCalculator/login_oauth'
    # Default to localhost:5000 to match StephenG753-OAuth.json
    return 'http://localhost:5000/TutoringCalculator/login_oauth'


def initiate_oauth_flow(redirect_uri, state=None):
    flow = Flow.from_client_secrets_file(
        OAUTH_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state
    )
    return auth_url


def process_oauth_callback(redirect_uri, authorization_response):
    flow = Flow.from_client_secrets_file(
        OAUTH_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials

    with open(TOKEN_PICKLE_FILE, 'wb') as token_file:
        pickle.dump(creds, token_file)

    return creds
