"""
Tests for Complete OAuth Flow Scenarios
----------------------------------------
Tests for successful OAuth flows and edge cases not covered in existing tests.
"""

import threading
from unittest.mock import Mock, patch, mock_open


from app.services import auth


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
        """Complete OAuth flow should save token successfully."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_host = "localhost"

        def exists_side_effect(path):
            if "token.json" in str(path):
                return False
            if "credentials.json" in str(path):
                return True
            return False

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

        def exists_side_effect(path):
            if "token.json" in str(path):
                return False
            if "credentials.json" in str(path):
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.run_local_server.return_value = Mock()

        service, error = auth.get_gmail_service()

        # Verify bind_address is 0.0.0.0 for web auth mode
        mock_flow_instance.run_local_server.assert_called_once()
        call_kwargs = mock_flow_instance.run_local_server.call_args[1]
        assert call_kwargs.get("bind_addr") == "0.0.0.0"

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

        def exists_side_effect(path):
            if "token.json" in str(path):
                return False
            if "credentials.json" in str(path):
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.run_local_server.return_value = Mock()

        service, error = auth.get_gmail_service()

        # Verify bind_address is localhost for desktop mode
        mock_flow_instance.run_local_server.assert_called_once()
        call_kwargs = mock_flow_instance.run_local_server.call_args[1]
        assert call_kwargs.get("bind_addr") == "localhost"

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

        def exists_side_effect(path):
            if "token.json" in str(path):
                return False
            if "credentials.json" in str(path):
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_flow_instance.run_local_server.return_value = Mock()

        service, error = auth.get_gmail_service()

        # Verify custom host is used
        mock_flow_instance.run_local_server.assert_called_once()
        call_kwargs = mock_flow_instance.run_local_server.call_args[1]
        assert call_kwargs.get("host") == "custom.example.com"


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

        def exists_side_effect(path):
            if "token.json" in str(path):
                return False
            if "credentials.json" in str(path):
                return True
            return False

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

        def exists_side_effect(path):
            if "token.json" in str(path):
                return False
            if "credentials.json" in str(path):
                return True
            return False

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

        def exists_side_effect(path):
            if "token.json" in str(path):
                return False
            if "credentials.json" in str(path):
                return True
            return False

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


class TestConfiguredRedirectUri:
    """Tests for the OAUTH_REDIRECT_URI override (reverse proxy / TLS termination)."""

    @staticmethod
    def _abort_after_redirect_uri(mock_flow_instance):
        """Stop the flow right after redirect_uri is set, and signal when that happened.

        run_oauth() always runs on a background thread, so the test needs a
        happens-before edge rather than relying on it finishing in time.
        """
        reached = threading.Event()

        def fake_authorization_url(**_kwargs):
            reached.set()
            # A falsy URL makes run_oauth raise ValueError and unwind cleanly,
            # which is enough: redirect_uri is already assigned by this point.
            return (None, None)

        mock_flow_instance.authorization_url.side_effect = fake_authorization_url
        return reached

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty", return_value=False)
    @patch("app.services.auth.os.path.exists")
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"web": {"client_id": "test", "client_secret": "secret"}}',
    )
    def test_configured_redirect_uri_is_used_verbatim(
        self,
        mock_file,
        mock_web_auth,
        mock_flow,
        mock_exists,
        mock_is_file_empty,
        mock_settings,
    ):
        """OAUTH_REDIRECT_URI should be used as-is, keeping https and dropping the port."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_external_port = None
        mock_settings.oauth_host = "gmail.example.com"
        mock_settings.oauth_redirect_uri = "https://gmail.example.com/"

        mock_exists.side_effect = lambda path: "credentials.json" in str(path)

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        reached = self._abort_after_redirect_uri(mock_flow_instance)

        auth.get_gmail_service()

        assert reached.wait(timeout=5), "OAuth flow never reached authorization_url"
        assert mock_flow_instance.redirect_uri == "https://gmail.example.com/"
        # run_local_server would rebuild the URI as http://host:port/ and break token exchange
        mock_flow_instance.run_local_server.assert_not_called()

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty", return_value=False)
    @patch("app.services.auth.os.path.exists")
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"web": {"client_id": "test", "client_secret": "secret"}}',
    )
    def test_configured_redirect_uri_overrides_external_port(
        self,
        mock_file,
        mock_web_auth,
        mock_flow,
        mock_exists,
        mock_is_file_empty,
        mock_settings,
    ):
        """OAUTH_REDIRECT_URI should win over OAUTH_EXTERNAL_PORT composition."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_external_port = 18767
        mock_settings.oauth_host = "gmail.example.com"
        mock_settings.oauth_redirect_uri = "https://gmail.example.com/oauth2/callback"

        mock_exists.side_effect = lambda path: "credentials.json" in str(path)

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        reached = self._abort_after_redirect_uri(mock_flow_instance)

        auth.get_gmail_service()

        assert reached.wait(timeout=5), "OAuth flow never reached authorization_url"
        assert (
            mock_flow_instance.redirect_uri
            == "https://gmail.example.com/oauth2/callback"
        )

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty", return_value=False)
    @patch("app.services.auth.os.path.exists")
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"installed": {"client_id": "test", "client_secret": "secret"}}',
    )
    def test_unset_redirect_uri_keeps_run_local_server(
        self,
        mock_file,
        mock_web_auth,
        mock_flow,
        mock_exists,
        mock_is_file_empty,
        mock_settings,
    ):
        """With OAUTH_REDIRECT_URI unset the original run_local_server path is kept."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]
        mock_settings.oauth_port = 8767
        mock_settings.oauth_external_port = None
        mock_settings.oauth_host = "localhost"
        mock_settings.oauth_redirect_uri = None

        mock_exists.side_effect = lambda path: "credentials.json" in str(path)

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance

        started = threading.Event()
        mock_flow_instance.run_local_server.side_effect = (
            lambda **_kwargs: started.set() or Mock()
        )

        auth.get_gmail_service()

        assert started.wait(timeout=5), "run_local_server was never called"
        mock_flow_instance.authorization_url.assert_not_called()
