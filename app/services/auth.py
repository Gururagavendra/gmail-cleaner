"""
Authentication Service
----------------------
Handles OAuth2 authentication with Gmail API.
"""

import os
import shutil
import threading

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.core import settings, state


# Track auth in progress
_auth_in_progress = {"active": False}


def is_web_auth_mode() -> bool:
    """Check if we should use web-based auth (for Docker/headless)."""
    return settings.web_auth


def needs_auth_setup() -> bool:
    """Check if authentication is needed."""
    if os.path.exists(settings.token_file):
        try:
            creds = Credentials.from_authorized_user_file(settings.token_file, settings.scopes)
            if creds and (creds.valid or creds.refresh_token):
                return False
        except Exception:
            pass
    return True


def get_web_auth_status() -> dict:
    """Get current web auth status."""
    return {
        "needs_setup": needs_auth_setup(),
        "web_auth_mode": is_web_auth_mode(),
        "has_credentials": os.path.exists(settings.credentials_file),
        "pending_auth_url": state.pending_auth_url.get("url")
    }


def _get_credentials_path() -> str | None:
    """Get credentials - from file or create from env var."""
    if os.path.exists(settings.credentials_file):
        return settings.credentials_file
    
    # Check for env var (for cloud deployment)
    env_creds = os.environ.get('GOOGLE_CREDENTIALS')
    if env_creds:
        with open(settings.credentials_file, 'w') as f:
            f.write(env_creds)
        return settings.credentials_file
    
    return None


def get_gmail_service():
    """Get authenticated Gmail API service.
    
    Returns:
        tuple: (service, error_message) - service is None if auth needed
    """
    creds = None
    
    if os.path.exists(settings.token_file):
        creds = Credentials.from_authorized_user_file(settings.token_file, settings.scopes)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(settings.token_file, 'w') as token:
                token.write(creds.to_json())
        else:
            # Prevent multiple OAuth attempts
            if _auth_in_progress["active"]:
                return None, "Sign-in already in progress. Please complete the authorization in your browser."
            
            creds_path = _get_credentials_path()
            if not creds_path:
                return None, "credentials.json not found! Please follow setup instructions."
            
            # Start OAuth in background thread so server stays responsive
            _auth_in_progress["active"] = True
            
            def run_oauth():
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(creds_path, settings.scopes)
                    
                    # Check if we have a browser available
                    has_browser = shutil.which('xdg-open') or shutil.which('open') or os.environ.get('DISPLAY')
                    
                    # For Docker: bind to 0.0.0.0 so callback can reach container
                    # For local: bind to localhost for security
                    bind_address = "0.0.0.0" if is_web_auth_mode() else "localhost"
                    
                    new_creds = flow.run_local_server(
                        port=settings.oauth_port,
                        bind_addr=bind_address,
                        open_browser=has_browser
                    )
                    
                    with open(settings.token_file, 'w') as token:
                        token.write(new_creds.to_json())
                    print("OAuth complete! Token saved.")
                except Exception as e:
                    print(f"OAuth error: {e}")
                finally:
                    _auth_in_progress["active"] = False
                    state.pending_auth_url["url"] = None
            
            oauth_thread = threading.Thread(target=run_oauth, daemon=True)
            oauth_thread.start()
            
            return None, "Sign-in started. Please complete authorization in your browser."
    
    service = build('gmail', 'v1', credentials=creds)
    
    try:
        profile = service.users().getProfile(userId='me').execute()
        state.current_user['email'] = profile.get('emailAddress', 'Unknown')
        state.current_user['logged_in'] = True
    except Exception:
        state.current_user['email'] = 'Unknown'
        state.current_user['logged_in'] = True
    
    return service, None


def sign_out() -> dict:
    """Sign out by removing the token file."""
    if os.path.exists(settings.token_file):
        os.remove(settings.token_file)
    
    # Reset state
    state.current_user = {"email": None, "logged_in": False}
    state.reset_scan()
    state.reset_delete_scan()
    state.reset_mark_read()
    
    print("Signed out - results cleared")
    return {"success": True, "message": "Signed out successfully", "results_cleared": True}


def check_login_status() -> dict:
    """Check if user is logged in and get their email."""
    if os.path.exists(settings.token_file):
        try:
            creds = Credentials.from_authorized_user_file(settings.token_file, settings.scopes)
            if creds and creds.valid:
                service = build('gmail', 'v1', credentials=creds)
                profile = service.users().getProfile(userId='me').execute()
                state.current_user['email'] = profile.get('emailAddress', 'Unknown')
                state.current_user['logged_in'] = True
                return state.current_user.copy()
            elif creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(settings.token_file, 'w') as token:
                    token.write(creds.to_json())
                service = build('gmail', 'v1', credentials=creds)
                profile = service.users().getProfile(userId='me').execute()
                state.current_user['email'] = profile.get('emailAddress', 'Unknown')
                state.current_user['logged_in'] = True
                return state.current_user.copy()
        except Exception:
            pass
    
    state.current_user['email'] = None
    state.current_user['logged_in'] = False
    return state.current_user.copy()
