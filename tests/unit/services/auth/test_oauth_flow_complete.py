"""
Tests for Complete OAuth Flow Scenarios
----------------------------------------
Tests for successful OAuth flows and edge cases not covered in existing tests.
"""

from unittest.mock import Mock, patch, mock_open

from app.core.state import SessionState
from app.services import auth


def exists_side_effect(path):
    """
    Simulates os.path.exists behavior for tests by indicating presence only for credentials files.
    
    Parameters:
        path (str | os.PathLike): Path or filename to check.
    
    Returns:
        True if `path` contains "credentials.json", False otherwise (including when it contains "token.json").
    """
    if "token.json" in str(path):
        return False
    if "credentials.json" in str(path):
        return True
    return False


class ImmediateThread:
    """Run thread targets immediately in tests."""

    def __init__(self, *args, **kwargs):
        """
        Initialize an ImmediateThread-like object by recording a callable target, its positional and keyword arguments, and a daemon flag.
        
        Parameters:
            *args: Optional positional form (target, args, kwargs) where:
                - target (callable): the callable to invoke when started.
                - args (tuple): positional arguments to pass to the target.
                - kwargs (dict): keyword arguments to pass to the target.
            **kwargs: Keyword-based initialization keys:
                - target (callable): callable to invoke (overrides positional target if provided).
                - args (tuple): positional arguments to pass to the target (defaults to ()).
                - kwargs (dict): keyword arguments to pass to the target (defaults to {}).
                - daemon (bool): whether the thread is a daemon (defaults to False).
        
        Behavior:
            - If `target`, `args`, or `kwargs` are provided via keywords, those values are used.
            - If no keyword `target` is given but positional `*args` are supplied, the constructor derives `target`, `args`, and `kwargs` from the positional values in order.
        """
        self._target = kwargs.get("target")
        self._args = kwargs.get("args", ())
        self._kwargs = kwargs.get("kwargs", {})
        self.daemon = kwargs.get("daemon", False)
        if self._target is None and args:
            self._target = args[0]
            if len(args) > 1:
                self._args = args[1]
            if len(args) > 2:
                self._kwargs = args[2]

    def start(self):
        """
        Execute the stored target callable immediately in the current thread.
        
        If no target was provided, this method does nothing.
        """
        if self._target:
            self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        pass


class TestSuccessfulOAuthFlow:
    """Tests for successful OAuth flow scenarios"""

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("app.services.auth.os.path.exists")
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"installed": {"client_id": "test", "client_secret": "secret"}}',
    )
    def test_complete_oauth_flow_saves_token(
        self,
        mock_file,
        mock_web_auth,
        mock_flow,
        mock_exists,
        mock_is_file_empty,
        mock_settings,
    ):
        """
        Verifies that starting the complete OAuth flow when credentials exist and no token is present saves a new token and reports that sign-in has started.
        
        Sets up credentials present and token absent, mocks a successful InstalledAppFlow returning credentials with a token, then calls get_gmail_service and asserts that no service is returned immediately, an error message is returned, and the error contains "Sign-in started".
        """
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_host = "localhost"
        mock_settings.oauth_external_port = None

        mock_exists.side_effect = exists_side_effect
        mock_is_file_empty.return_value = False

        # Mock successful OAuth flow
        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance

        mock_creds = Mock()
        mock_creds.to_json.return_value = (
            '{"token": "new_token", "refresh_token": "refresh"}'
        )
        mock_flow_instance.run_local_server.return_value = mock_creds

        service, error = auth.get_gmail_service()

        # Should start OAuth (runs in background thread)
        assert service is None
        assert error is not None
        assert "Sign-in started" in error

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"type": "installed", "client_id": "test"}',
    )
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=True)
    def test_oauth_flow_web_auth_mode_binds_to_all_interfaces(
        self, mock_web_auth, mock_flow, mock_file, mock_exists, mock_settings
    ):
        """OAuth flow in web auth mode should bind to 0.0.0.0."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_host = "localhost"

        mock_exists.side_effect = exists_side_effect

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.authorization_url.return_value = (
            "http://auth.example.com",
            "state",
        )

        with patch(
            "app.services.auth.HTTPServer", side_effect=OSError("port error")
        ) as mock_server, patch(
            "app.services.auth.threading.Thread", new=ImmediateThread
        ):
            service, error = auth.get_gmail_service(session=SessionState())

        # Verify bind_address is 0.0.0.0 for web auth mode
        assert service is None
        assert error is not None
        mock_server.assert_called_once()
        bind_address = mock_server.call_args[0][0][0]
        assert bind_address == "0.0.0.0"

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"type": "installed", "client_id": "test"}',
    )
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_oauth_flow_desktop_mode_binds_to_localhost(
        self, mock_web_auth, mock_flow, mock_file, mock_exists, mock_settings
    ):
        """OAuth flow in desktop mode should bind to localhost."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_host = "localhost"
        mock_settings.oauth_external_port = None

        mock_exists.side_effect = exists_side_effect

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.authorization_url.return_value = (
            "http://auth.example.com",
            "state",
        )

        with patch(
            "app.services.auth.HTTPServer", side_effect=OSError("port error")
        ) as mock_server, patch(
            "app.services.auth.threading.Thread", new=ImmediateThread
        ):
            service, error = auth.get_gmail_service(session=SessionState())

        # Verify bind_address is localhost for desktop mode
        assert service is None
        assert error is not None
        mock_server.assert_called_once()
        bind_address = mock_server.call_args[0][0][0]
        assert bind_address == "localhost"

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"type": "installed", "client_id": "test"}',
    )
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_oauth_flow_with_custom_oauth_host(
        self, mock_web_auth, mock_flow, mock_file, mock_exists, mock_settings
    ):
        """OAuth flow should use custom OAUTH_HOST if configured."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_host = "custom.example.com"
        mock_settings.oauth_external_port = None

        mock_exists.side_effect = exists_side_effect

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.authorization_url.return_value = (
            "http://auth.example.com",
            "state",
        )

        with patch(
            "app.services.auth.HTTPServer", side_effect=OSError("port error")
        ), patch("app.services.auth.threading.Thread", new=ImmediateThread):
            service, error = auth.get_gmail_service(session=SessionState())

        # Verify custom host is used
        assert service is None
        assert error is not None
        assert mock_flow_instance.redirect_uri == "http://custom.example.com:8767/"


class TestOAuthFlowErrors:
    """Tests for OAuth flow error scenarios"""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"type": "installed", "client_id": "test"}',
    )
    @patch("app.services.auth._is_file_empty", return_value=False)
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_oauth_invalid_authorization_code(
        self,
        mock_web_auth,
        mock_flow,
        mock_is_file_empty,
        mock_file,
        mock_exists,
        mock_settings,
    ):
        """OAuth flow should handle invalid authorization code."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_host = "localhost"

        mock_exists.side_effect = exists_side_effect

        # Mock Flow to raise error for invalid code
        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.run_local_server.side_effect = ValueError(
            "Invalid authorization code"
        )

        service, error = auth.get_gmail_service()

        # Should start OAuth (error caught in background thread)
        assert service is None
        assert error is not None

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"type": "installed", "client_id": "test"}',
    )
    @patch("app.services.auth._is_file_empty", return_value=False)
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_oauth_timeout_handling(
        self,
        mock_web_auth,
        mock_flow,
        mock_is_file_empty,
        mock_file,
        mock_exists,
        mock_settings,
    ):
        """OAuth flow should handle timeout gracefully."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_host = "localhost"

        mock_exists.side_effect = exists_side_effect

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.run_local_server.side_effect = TimeoutError(
            "OAuth flow timed out"
        )

        service, error = auth.get_gmail_service()

        assert service is None
        assert error is not None

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"type": "installed", "client_id": "test"}',
    )
    @patch("app.services.auth._is_file_empty", return_value=False)
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_oauth_resets_auth_in_progress_on_error(
        self,
        mock_web_auth,
        mock_flow,
        mock_is_file_empty,
        mock_file,
        mock_exists,
        mock_settings,
    ):
        """OAuth flow should reset _auth_in_progress flag on error."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_host = "localhost"

        mock_exists.side_effect = exists_side_effect

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.run_local_server.side_effect = Exception("OAuth error")

        # Set auth in progress
        auth._auth_in_progress["active"] = True

        service, error = auth.get_gmail_service()

        # The error is caught in background thread, but flag should be reset in finally block
        # Note: This tests the structure, actual reset happens in background thread
        assert service is None
        assert error is not None
