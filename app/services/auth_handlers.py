"""
OAuth Callback Handlers
-----------------------
HTTP request handlers for OAuth2 callback processing.
"""

import logging
from http.server import BaseHTTPRequestHandler
from threading import Event, Lock
from urllib.parse import parse_qs, urlparse

from app.core import state

logger = logging.getLogger(__name__)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth2 callback processing.

    This handler processes OAuth2 callbacks, validates CSRF state tokens,
    and communicates results back to the main OAuth flow via thread-safe
    primitives.

    Args:
        callback_event: Threading event to signal callback completion
        callback_lock: Threading lock to protect shared callback data
        callback_data: Dictionary to store callback results (code/error)
    """

    def __init__(
        self,
        callback_event: Event,
        callback_lock: Lock,
        callback_data: dict,
        *args,
        **kwargs,
    ):
        """Initialize the handler with thread-safe callback primitives."""
        self.callback_event = callback_event
        self.callback_lock = callback_lock
        self.callback_data = callback_data
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET request for OAuth callback."""
        # Prevent processing multiple callbacks
        with self.callback_lock:
            if self.callback_event.is_set():
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Callback already processed</h1><p>You can close this window.</p></body></html>"
                )
                return

        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        # Verify OAuth state for CSRF protection
        stored_state = state.get_oauth_state().get("state")
        incoming_state = None
        if "state" in query_params:
            state_list = query_params["state"]
            if state_list and len(state_list) > 0:
                incoming_state = state_list[0]

        # Verify state matches stored state
        if stored_state is None:
            logger.error(
                "OAuth callback received but no stored state found - possible CSRF attack or state expired"
            )
            with self.callback_lock:
                self.callback_data["error"] = (
                    "OAuth callback received but no stored state found - possible CSRF attack or state expired"
                )
                # Clear state on security error
                state.set_oauth_state(None)
                self.callback_event.set()
            self.send_response(403)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Security Error</h1><p>Authentication state mismatch. Please try signing in again.</p></body></html>"
            )
            return

        if incoming_state is None:
            logger.error(
                "OAuth callback missing state parameter - possible CSRF attack or malformed request"
            )
            with self.callback_lock:
                self.callback_data["error"] = (
                    "OAuth callback missing state parameter - possible CSRF attack or malformed request"
                )
                # Clear state on security error
                state.set_oauth_state(None)
                self.callback_event.set()
            self.send_response(403)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Security Error</h1><p>Authentication state mismatch. Please try signing in again.</p></body></html>"
            )
            return

        if incoming_state != stored_state:
            logger.error(
                "OAuth state mismatch - possible CSRF attack. "
                "Expected: %s..., Received: %s...",
                stored_state[:20] if len(stored_state) > 20 else stored_state,
                incoming_state[:20] if len(incoming_state) > 20 else incoming_state,
            )
            with self.callback_lock:
                self.callback_data["error"] = (
                    "OAuth state mismatch - possible CSRF attack"
                )
                # Clear state on security error to prevent reuse
                state.set_oauth_state(None)
                self.callback_event.set()
            self.send_response(403)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Security Error</h1><p>Authentication state mismatch. Please try signing in again.</p></body></html>"
            )
            return

        if "code" in query_params:
            code_list = query_params["code"]
            if code_list and len(code_list) > 0:
                with self.callback_lock:
                    self.callback_data["code"] = code_list[0]
                    # Clear OAuth state after successful verification
                    state.set_oauth_state(None)
                    self.callback_event.set()
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authentication successful!</h1><p>You can close this window.</p></body></html>"
                )
            else:
                # Empty code parameter - invalid request
                with self.callback_lock:
                    self.callback_data["error"] = "Empty authorization code"
                    self.callback_data["code"] = None
                    state.set_oauth_state(None)
                    self.callback_event.set()
                logger.warning("OAuth callback received empty code parameter")
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Invalid request - empty authorization code</h1><p>You can close this window.</p></body></html>"
                )
        elif "error" in query_params:
            error_list = query_params["error"]
            if error_list and len(error_list) > 0:
                error_message = error_list[0]
                error_description = query_params.get("error_description", [""])
                error_description = error_description[0] if error_description else ""
                with self.callback_lock:
                    self.callback_data["error"] = error_message + (
                        f" - {error_description}" if error_description else ""
                    )
                    # Clear OAuth state on error
                    state.set_oauth_state(None)
                    self.callback_event.set()
                logger.error(
                    f"OAuth callback error: {error_message}"
                    + (f" - {error_description}" if error_description else "")
                )
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authentication failed!</h1><p>You can close this window.</p></body></html>"
                )
            else:
                # Empty error parameter - invalid request
                with self.callback_lock:
                    self.callback_data["error"] = "Empty error parameter received"
                    self.callback_data["code"] = None
                    state.set_oauth_state(None)
                    self.callback_event.set()
                logger.warning("OAuth callback received empty error parameter")
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Invalid request - empty error parameter</h1><p>You can close this window.</p></body></html>"
                )
        else:
            # Invalid request - don't mark as received to allow retry
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Invalid request</h1><p>You can close this window.</p></body></html>"
            )
