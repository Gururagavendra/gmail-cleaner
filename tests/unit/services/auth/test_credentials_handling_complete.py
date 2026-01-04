"""
Tests for Complete Credentials Handling Scenarios
--------------------------------------------------
Tests for credentials file handling, environment variables, and validation.
"""

import os
from unittest.mock import Mock, patch, mock_open


from app.services import auth


class TestCredentialsFromEnvironmentVariable:
    """Tests for credentials from GOOGLE_CREDENTIALS environment variable"""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch.dict(
        os.environ,
        {"GOOGLE_CREDENTIALS": '{"type": "installed", "client_id": "test"}'},
        clear=False,
    )
    def test_credentials_from_env_var_creates_file(
        self, mock_file, mock_exists, mock_settings
    ):
        """Credentials from GOOGLE_CREDENTIALS env var should create credentials.json."""
        mock_settings.credentials_file = "credentials.json"

        def exists_side_effect(path):
            if "credentials.json" in str(path):
                return False
            return False

        mock_exists.side_effect = exists_side_effect

        result = auth._get_credentials_path()

        assert result == "credentials.json"
        # Verify file was written with env var content
        mock_file.assert_called_once_with("credentials.json", "w")
        mock_file.return_value.write.assert_called_once_with(
            '{"type": "installed", "client_id": "test"}'
        )

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch.dict(
        os.environ, {"GOOGLE_CREDENTIALS": '{"type": "installed"}'}, clear=False
    )
    def test_credentials_env_var_write_error(self, mock_exists, mock_settings):
        """Error writing credentials from env var should be handled."""
        from unittest.mock import patch

        mock_settings.credentials_file = "credentials.json"

        mock_exists.return_value = False

        # File write errors are now caught and return None (fixed behavior)
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            result = auth._get_credentials_path()
            # Should return None when write fails (error is logged)
            assert result is None

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch.dict(os.environ, {"GOOGLE_CREDENTIALS": ""}, clear=False)
    def test_credentials_env_var_empty_value(self, mock_exists, mock_settings):
        """Empty GOOGLE_CREDENTIALS env var should return None (empty string is falsy)."""
        mock_settings.credentials_file = "credentials.json"

        mock_exists.return_value = False

        result = auth._get_credentials_path()

        # Empty string is falsy, so returns None (fixed behavior)
        assert result is None

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch.dict(os.environ, {"GOOGLE_CREDENTIALS": "invalid json"}, clear=False)
    def test_credentials_env_var_invalid_json(self, mock_exists, mock_settings):
        """Invalid JSON in GOOGLE_CREDENTIALS should return None (validation happens before writing)."""
        mock_settings.credentials_file = "credentials.json"

        mock_exists.return_value = False

        result = auth._get_credentials_path()

        # Invalid JSON is validated before writing, so returns None
        assert result is None


class TestCredentialsFilePrecedence:
    """Tests for credentials file precedence over environment variable"""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"type": "installed", "client_id": "test"}',
    )
    @patch.dict(os.environ, {"GOOGLE_CREDENTIALS": '{"type": "env"}'}, clear=False)
    def test_credentials_file_takes_precedence_over_env(
        self, mock_file, mock_exists, mock_settings
    ):
        """Credentials file should take precedence over environment variable."""
        mock_settings.credentials_file = "credentials.json"

        def exists_side_effect(path):
            if "credentials.json" in str(path):
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        result = auth._get_credentials_path()

        # Should return file path, not create from env var
        assert result == "credentials.json"


class TestCredentialsValidation:
    """Tests for credentials validation scenarios"""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_credentials_missing_client_id(
        self, mock_web_auth, mock_flow, mock_exists, mock_settings
    ):
        """Credentials missing client ID should fail during OAuth initialization."""
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

        # Mock Flow to raise error for missing client ID
        mock_flow.from_client_secrets_file.side_effect = ValueError(
            "Missing required OAuth client_id"
        )

        service, error = auth.get_gmail_service()

        # Should start OAuth but error caught in background thread
        assert service is None
        assert error is not None

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_credentials_missing_client_secret(
        self, mock_web_auth, mock_flow, mock_exists, mock_settings
    ):
        """Credentials missing client secret should fail during OAuth initialization."""
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

        mock_flow.from_client_secrets_file.side_effect = ValueError(
            "Missing required OAuth client_secret"
        )

        service, error = auth.get_gmail_service()

        assert service is None
        assert error is not None

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_credentials_invalid_redirect_uri(
        self, mock_web_auth, mock_flow, mock_exists, mock_settings
    ):
        """Credentials with invalid redirect URI should fail during OAuth callback."""
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
        mock_flow_instance.run_local_server.side_effect = ValueError(
            "Redirect URI mismatch"
        )

        service, error = auth.get_gmail_service()

        assert service is None
        assert error is not None


class TestCredentialsFilePermissions:
    """Tests for credentials file permission scenarios"""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.InstalledAppFlow")
    @patch("app.services.auth._auth_in_progress", {"active": False})
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_credentials_file_read_permission_denied(
        self, mock_web_auth, mock_flow, mock_exists, mock_settings
    ):
        """Credentials file with read permission denied should be handled."""
        mock_settings.credentials_file = "credentials.json"
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        def exists_side_effect(path):
            if "token.json" in str(path):
                return False
            if "credentials.json" in str(path):
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        # Mock Flow to raise permission error
        mock_flow.from_client_secrets_file.side_effect = PermissionError(
            "Permission denied"
        )

        service, error = auth.get_gmail_service()

        # Error caught in background thread
        assert service is None
        assert error is not None


class TestCredentialsTypeMismatch:
    """Tests for credentials type mismatches"""

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
    def test_web_credentials_in_docker_mode(
        self, mock_web_auth, mock_flow, mock_file, mock_exists, mock_settings
    ):
        """Web application credentials should work in Docker/web auth mode."""
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

        # Should work with web credentials in web auth mode
        assert service is None
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
    @patch("app.services.auth.is_web_auth_mode", return_value=False)
    def test_desktop_credentials_in_local_mode(
        self, mock_web_auth, mock_flow, mock_file, mock_exists, mock_settings
    ):
        """Desktop app credentials should work in local mode."""
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

        # Should work with desktop credentials in local mode
        assert service is None
        assert "Sign-in started" in error
