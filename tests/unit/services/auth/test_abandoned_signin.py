"""
Tests for Abandoned OAuth Sign-ins
-----------------------------------
`run_local_server()` used to wait forever, so a user who closed the Google
consent screen left `_auth_in_progress` latched and every later sign-in was
refused until the process restarted.
"""

from unittest.mock import Mock, patch, mock_open

from app.services import auth


class _InlineThread:
    """Stand-in for threading.Thread that runs the target synchronously.

    The OAuth flow runs on a background thread, which makes assertions racy.
    Running it inline keeps these tests deterministic.
    """

    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        self._target()


def _configure_settings(mock_settings):
    mock_settings.credentials_file = "credentials.json"
    mock_settings.token_file = "token.json"
    mock_settings.scopes = ["scope1"]
    mock_settings.oauth_port = 8767
    mock_settings.oauth_host = "localhost"
    mock_settings.oauth_external_port = None


def _only_credentials_exist(path):
    if "token.json" in str(path):
        return False
    if "credentials.json" in str(path):
        return True
    return False


class TestAbandonedSignInReleasesLock:
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
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_local_server_is_given_a_deadline(
        self, mock_web_auth, mock_flow, mock_file, mock_exists, mock_settings
    ):
        """Without a deadline the callback server waits forever."""
        _configure_settings(mock_settings)
        mock_exists.side_effect = _only_credentials_exist

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.run_local_server.return_value = Mock()

        auth.get_gmail_service()

        call_kwargs = mock_flow_instance.run_local_server.call_args[1]
        assert call_kwargs.get("timeout_seconds") == auth.OAUTH_TIMEOUT_SECONDS

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
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_timeout_is_reported_as_a_timeout_and_frees_the_lock(
        self, mock_web_auth, mock_flow, mock_file, mock_exists, mock_settings, caplog
    ):
        """A timed-out server must not surface as a bare AttributeError."""
        _configure_settings(mock_settings)
        mock_exists.side_effect = _only_credentials_exist

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        # What google-auth-oauthlib actually raises when no callback arrives:
        # `wsgi_app.last_request_uri` is still None and gets .replace()'d.
        mock_flow_instance.run_local_server.side_effect = AttributeError(
            "'NoneType' object has no attribute 'replace'"
        )

        auth.get_gmail_service()

        assert "OAuth timeout" in caplog.text
        # The lock must be released so the next sign-in is not refused.
        assert auth._auth_in_progress["active"] is False

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
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_unrelated_attribute_errors_are_not_swallowed(
        self, mock_web_auth, mock_flow, mock_file, mock_exists, mock_settings, caplog
    ):
        """Only the timeout signature is reinterpreted, not every AttributeError."""
        _configure_settings(mock_settings)
        mock_exists.side_effect = _only_credentials_exist

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.run_local_server.side_effect = AttributeError(
            "'Flow' object has no attribute 'credentials'"
        )

        auth.get_gmail_service()

        assert "OAuth timeout" not in caplog.text
        assert auth._auth_in_progress["active"] is False
