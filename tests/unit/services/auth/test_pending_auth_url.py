"""
Tests for Publishing the OAuth Authorization URL
------------------------------------------------
The consent URL used to be printed to the container logs only, which forced
Docker/Kubernetes users to run `docker logs` to sign in. These tests cover
publishing it to `state.pending_auth_url` so the web UI can render it.
"""

import inspect
from unittest.mock import Mock, patch, mock_open

import pytest
from google_auth_oauthlib.flow import InstalledAppFlow

from app.core import state
from app.services import auth


AUTH_URL = "https://accounts.google.com/o/oauth2/auth?client_id=test&state=abc"


class _InlineThread:
    """Stand-in for threading.Thread that runs the target synchronously.

    The OAuth flow runs on a background thread, which makes assertions racy.
    Running it inline keeps these tests deterministic.
    """

    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        self._target()


@pytest.fixture(autouse=True)
def reset_pending_auth_url():
    """Keep the global auth URL state from leaking between tests."""
    state.pending_auth_url["url"] = None
    yield
    state.pending_auth_url["url"] = None


def _configure_settings(mock_settings, external_port=None):
    mock_settings.credentials_file = "credentials.json"
    mock_settings.token_file = "token.json"
    mock_settings.scopes = ["scope1"]
    mock_settings.oauth_port = 8767
    mock_settings.oauth_host = "localhost"
    mock_settings.oauth_external_port = external_port


def _only_credentials_exist(path):
    if "token.json" in str(path):
        return False
    if "credentials.json" in str(path):
        return True
    return False


class TestRunLocalServerPath:
    """The default path (oauth_port == redirect port) uses run_local_server."""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"installed": {"client_id": "test"}}',
    )
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth.threading.Thread", _InlineThread)
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=True)
    def test_publishes_url_while_waiting_for_consent(
        self, mock_web_auth, mock_flow, mock_file, mock_exists, mock_settings
    ):
        """The URL run_local_server builds internally must reach the UI state."""
        _configure_settings(mock_settings)
        mock_exists.side_effect = _only_credentials_exist

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.authorization_url.return_value = (AUTH_URL, "state-token")

        seen = {}

        def fake_run_local_server(**kwargs):
            # Mirror what google-auth-oauthlib does internally.
            mock_flow_instance.authorization_url(prompt="consent")
            seen["url"] = state.pending_auth_url["url"]
            return Mock()

        mock_flow_instance.run_local_server.side_effect = fake_run_local_server

        auth.get_gmail_service()

        # Published while the user is being asked to consent...
        assert seen.get("url") == AUTH_URL
        # ...and cleared once the flow finishes.
        assert state.pending_auth_url["url"] is None


class TestCustomRedirectPortPath:
    """The manual path (custom external port) publishes in every auth mode."""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"installed": {"client_id": "test"}}',
    )
    @patch("app.services.auth.HTTPServer")
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth.threading.Thread", _InlineThread)
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_publishes_url_outside_web_auth_mode(
        self,
        mock_web_auth,
        mock_flow,
        mock_http_server,
        mock_file,
        mock_exists,
        mock_settings,
    ):
        """Desktop users whose browser fails to open still need the URL."""
        _configure_settings(mock_settings, external_port=18767)
        mock_exists.side_effect = _only_credentials_exist

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.authorization_url.return_value = (AUTH_URL, "state-token")

        seen = {}

        def stop_after_publish(*args, **kwargs):
            # The URL is published before the callback server starts; capture it
            # there and abort rather than blocking on a real callback.
            seen["url"] = state.pending_auth_url["url"]
            raise OSError("stop the flow here")

        mock_http_server.side_effect = stop_after_publish

        auth.get_gmail_service()

        assert seen.get("url") == AUTH_URL


class TestPublishAuthorizationUrlHelper:
    """Direct tests for the wrapper installed around Flow.authorization_url."""

    def test_wrapper_matches_the_real_library_contract(self):
        """Run against a genuine Flow so a changed return shape is caught."""
        client_config = {
            "installed": {
                "client_id": "fake-id.apps.googleusercontent.com",
                "client_secret": "fake-secret",  # nosec B105 - not a real secret
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        flow = InstalledAppFlow.from_client_config(
            client_config, scopes=["https://www.googleapis.com/auth/gmail.readonly"]
        )
        flow.redirect_uri = "http://localhost:8767/"

        auth._publish_authorization_url(flow)
        url, _ = flow.authorization_url(prompt="consent")

        assert url.startswith("https://accounts.google.com/o/oauth2/auth")
        assert state.pending_auth_url["url"] == url

    def test_run_local_server_still_builds_its_url_via_authorization_url(self):
        """Guard the dependency internal this feature hooks into.

        `_publish_authorization_url` works by wrapping `Flow.authorization_url`,
        which `run_local_server` calls to build the consent URL. If an upgrade
        of google-auth-oauthlib changes that, the URL silently stops reaching
        the UI - so fail loudly here instead.
        """
        source = inspect.getsource(InstalledAppFlow.run_local_server)
        assert "self.authorization_url(" in source

    def test_unexpected_return_shape_does_not_break_the_flow(self):
        """A changed return type must not take the whole sign-in down."""
        flow = Mock()
        flow.authorization_url.return_value = None

        auth._publish_authorization_url(flow)
        result = flow.authorization_url()

        assert result is None
        assert state.pending_auth_url["url"] is None


class TestWebAuthStatusExposesUrl:
    """The status endpoint is how the browser learns about the URL."""

    @patch("app.services.auth.settings")
    @patch("app.services.auth.needs_auth_setup", return_value=True)
    @patch("app.services.auth.os.path.exists", return_value=True)
    def test_status_reports_the_pending_url(
        self, mock_exists, mock_needs_setup, mock_settings
    ):
        _configure_settings(mock_settings)
        state.pending_auth_url["url"] = AUTH_URL

        status = auth.get_web_auth_status()

        assert status["pending_auth_url"] == AUTH_URL
