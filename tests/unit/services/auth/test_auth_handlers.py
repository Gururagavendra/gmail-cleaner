"""
Tests for OAuth Callback Handlers
---------------------------------
Tests for auth_handlers.py - OAuth2 callback processing.
"""

import io
from threading import Event, Lock
from typing import Optional
from unittest.mock import Mock, patch, MagicMock, PropertyMock

import pytest


def create_mock_handler(
    path: str,
    callback_event: Optional[Event] = None,
    callback_lock: Optional[Lock] = None,
    callback_data: Optional[dict] = None,
):
    """Create a mock OAuthCallbackHandler with the given path."""
    from app.services.auth_handlers import OAuthCallbackHandler

    if callback_event is None:
        callback_event = Event()
    if callback_lock is None:
        callback_lock = Lock()
    if callback_data is None:
        callback_data = {}

    # We need to patch the handler's initialization since BaseHTTPRequestHandler
    # tries to handle the request immediately in __init__
    with patch.object(OAuthCallbackHandler, '__init__', lambda self, *args, **kwargs: None):
        handler = OAuthCallbackHandler.__new__(OAuthCallbackHandler)

    # Set up the handler attributes manually
    handler.callback_event = callback_event
    handler.callback_lock = callback_lock
    handler.callback_data = callback_data
    handler.path = path
    handler.wfile = io.BytesIO()
    handler.requestline = f"GET {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.command = "GET"

    # Mock the response methods
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()

    return handler


class TestOAuthCallbackHandler:
    """Tests for OAuthCallbackHandler class."""

    def test_callback_already_processed(self):
        """Already processed callback should return early."""
        callback_event = Event()
        callback_event.set()  # Mark as already processed
        callback_data = {}

        handler = create_mock_handler(
            "/?code=test_code&state=test_state",
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        handler.send_response.assert_called_with(200)
        assert b"already processed" in handler.wfile.getvalue()

    @patch("app.services.auth_handlers.state")
    def test_no_stored_state(self, mock_state):
        """Missing stored state should return 403."""
        callback_data = {}
        callback_event = Event()

        # Mock get_oauth_state to return no stored state
        mock_state.get_oauth_state.return_value = {"state": None}

        handler = create_mock_handler(
            "/?code=test_code&state=incoming_state",
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        handler.send_response.assert_called_with(403)
        assert callback_data.get("error") is not None
        assert "no stored state" in callback_data["error"]
        assert callback_event.is_set()
        mock_state.set_oauth_state.assert_called_with(None)

    @patch("app.services.auth_handlers.state")
    def test_missing_incoming_state(self, mock_state):
        """Missing incoming state parameter should return 403."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "stored_state_value"}

        handler = create_mock_handler(
            "/?code=test_code",  # No state parameter
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        handler.send_response.assert_called_with(403)
        assert callback_data.get("error") is not None
        assert "missing state" in callback_data["error"]
        assert callback_event.is_set()

    @patch("app.services.auth_handlers.state")
    def test_state_mismatch(self, mock_state):
        """State mismatch should return 403."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "correct_state"}

        handler = create_mock_handler(
            "/?code=test_code&state=wrong_state",
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        handler.send_response.assert_called_with(403)
        assert callback_data.get("error") is not None
        assert "mismatch" in callback_data["error"]
        assert callback_event.is_set()

    @patch("app.services.auth_handlers.state")
    def test_successful_code_callback(self, mock_state):
        """Successful code callback should return 200 and set code."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "matching_state"}

        handler = create_mock_handler(
            "/?code=authorization_code_123&state=matching_state",
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        handler.send_response.assert_called_with(200)
        assert callback_data.get("code") == "authorization_code_123"
        assert callback_event.is_set()
        assert b"successful" in handler.wfile.getvalue()

    @patch("app.services.auth_handlers.state")
    def test_empty_code_parameter(self, mock_state):
        """Empty code parameter is treated as invalid request by parse_qs."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "matching_state"}

        # parse_qs ignores empty values, so code= is treated as no code
        handler = create_mock_handler(
            "/?code=&state=matching_state",  # Empty code
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        # Empty code falls through to invalid request (no code or error)
        handler.send_response.assert_called_with(400)
        assert not callback_event.is_set()
        assert b"Invalid request" in handler.wfile.getvalue()

    @patch("app.services.auth_handlers.state")
    def test_oauth_error_callback(self, mock_state):
        """OAuth error callback should return 400 and set error."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "matching_state"}

        handler = create_mock_handler(
            "/?error=access_denied&state=matching_state",
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        handler.send_response.assert_called_with(400)
        assert "access_denied" in callback_data.get("error", "")
        assert callback_event.is_set()

    @patch("app.services.auth_handlers.state")
    def test_oauth_error_with_description(self, mock_state):
        """OAuth error with description should include it."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "matching_state"}

        handler = create_mock_handler(
            "/?error=access_denied&error_description=User%20denied%20access&state=matching_state",
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        handler.send_response.assert_called_with(400)
        assert "access_denied" in callback_data.get("error", "")
        assert "User denied access" in callback_data.get("error", "")
        assert callback_event.is_set()

    @patch("app.services.auth_handlers.state")
    def test_empty_error_parameter(self, mock_state):
        """Empty error parameter is treated as invalid request by parse_qs."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "matching_state"}

        # parse_qs ignores empty values, so error= is treated as no error
        handler = create_mock_handler(
            "/?error=&state=matching_state",  # Empty error
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        # Empty error falls through to invalid request (no code or error)
        handler.send_response.assert_called_with(400)
        assert not callback_event.is_set()
        assert b"Invalid request" in handler.wfile.getvalue()

    @patch("app.services.auth_handlers.state")
    def test_invalid_request_no_code_or_error(self, mock_state):
        """Request without code or error should return 400."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "matching_state"}

        handler = create_mock_handler(
            "/?state=matching_state",  # No code or error
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        handler.send_response.assert_called_with(400)
        # Event should NOT be set for invalid requests (allows retry)
        assert not callback_event.is_set()
        assert b"Invalid request" in handler.wfile.getvalue()

    @patch("app.services.auth_handlers.state")
    def test_state_cleared_on_success(self, mock_state):
        """OAuth state should be cleared after successful callback."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "matching_state"}

        handler = create_mock_handler(
            "/?code=auth_code&state=matching_state",
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        # set_oauth_state should be called with None on success
        mock_state.set_oauth_state.assert_called_with(None)

    @patch("app.services.auth_handlers.state")
    def test_state_cleared_on_error(self, mock_state):
        """OAuth state should be cleared on security errors."""
        callback_data = {}
        callback_event = Event()

        mock_state.get_oauth_state.return_value = {"state": "stored_state"}

        handler = create_mock_handler(
            "/?code=auth_code&state=wrong_state",  # Mismatched state
            callback_event=callback_event,
            callback_data=callback_data,
        )

        handler.do_GET()

        # set_oauth_state should be called with None on security error
        mock_state.set_oauth_state.assert_called_with(None)

    @patch("app.services.auth_handlers.state")
    def test_long_state_truncation_in_log(self, mock_state):
        """Long state values should be handled without errors."""
        callback_data = {}
        callback_event = Event()

        # Use states longer than 20 characters
        long_stored_state = "a" * 30
        long_incoming_state = "b" * 30

        mock_state.get_oauth_state.return_value = {"state": long_stored_state}

        handler = create_mock_handler(
            f"/?code=auth_code&state={long_incoming_state}",
            callback_event=callback_event,
            callback_data=callback_data,
        )

        # Should not raise even with long states
        handler.do_GET()

        handler.send_response.assert_called_with(403)
        assert "mismatch" in callback_data.get("error", "")
