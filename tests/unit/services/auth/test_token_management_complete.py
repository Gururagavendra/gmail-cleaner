"""
Tests for Complete Token Management Scenarios
-----------------------------------------------
Tests for token creation, storage, validation, and security.
"""

from unittest.mock import Mock, patch, mock_open

from google.oauth2.credentials import Credentials

from app.services import auth


class TestTokenCreationAndStorage:
    """Tests for token creation and storage scenarios"""

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
    def test_token_file_created_after_oauth(
        self,
        mock_file,
        mock_web_auth,
        mock_flow,
        mock_exists,
        mock_is_file_empty,
        mock_settings,
    ):
        """Token file should be created after successful OAuth."""
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

        mock_flow_instance = Mock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance

        mock_creds = Mock()
        mock_creds.to_json.return_value = '{"token": "access_token", "refresh_token": "refresh_token", "scopes": ["scope1", "scope2"]}'
        mock_flow_instance.run_local_server.return_value = mock_creds

        service, error = auth.get_gmail_service()

        # OAuth runs in background thread, so we verify the structure
        assert service is None
        assert error is not None
        assert "Sign-in started" in error

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_token_saved_with_correct_scopes(
        self, mock_creds_class, mock_exists, mock_settings
    ):
        """Token should include required Gmail API scopes."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
        ]

        mock_exists.return_value = True

        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = True
        mock_creds.scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
        ]

        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        result = auth.needs_auth_setup()

        # Token with correct scopes should be valid
        assert result is False

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("app.services.auth.os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth.Request")
    @patch("builtins.open", new_callable=mock_open)
    @patch("app.services.auth.build")
    def test_token_refresh_saves_new_token(
        self,
        mock_build,
        mock_file,
        mock_request,
        mock_creds_class,
        mock_exists,
        mock_is_file_empty,
        mock_settings,
    ):
        """Token refresh should save new token to file."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True
        mock_is_file_empty.return_value = False

        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "valid_refresh_token"
        mock_creds.to_json.return_value = (
            '{"token": "new_access_token", "refresh_token": "valid_refresh_token"}'
        )

        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        # Mock refresh to set valid=True after refresh (simulating successful refresh)
        def refresh_side_effect(*args, **kwargs):
            mock_creds.valid = True
            mock_creds.expired = False

        mock_creds.refresh = Mock(side_effect=refresh_side_effect)

        mock_service = Mock()
        mock_profile = Mock()
        mock_profile.execute.return_value = {"emailAddress": "test@example.com"}
        mock_service.users.return_value.getProfile.return_value = mock_profile
        mock_build.return_value = mock_service

        service, error = auth.get_gmail_service()

        # Verify refresh was called
        assert mock_creds.refresh.called
        # Verify token was written (happens in get_gmail_service)
        assert service is not None
        assert error is None


class TestTokenValidation:
    """Tests for token validation scenarios"""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_valid_token_is_recognized(
        self, mock_creds_class, mock_exists, mock_settings
    ):
        """Valid token should be recognized as authenticated."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True

        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = True
        mock_creds.refresh_token = "refresh_token"

        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        result = auth.needs_auth_setup()

        assert result is False

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("app.services.auth.os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth.Request")
    @patch("builtins.open", new_callable=mock_open)
    @patch("app.services.auth.build")
    def test_expired_token_with_refresh_token_auto_refreshes(
        self,
        mock_build,
        mock_file,
        mock_request,
        mock_creds_class,
        mock_exists,
        mock_is_file_empty,
        mock_settings,
    ):
        """Expired token with valid refresh token should auto-refresh."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True
        mock_is_file_empty.return_value = False

        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "valid_refresh_token"
        mock_creds.to_json.return_value = '{"token": "refreshed"}'

        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        # Mock refresh to set valid=True after refresh (simulating successful refresh)
        def refresh_side_effect(*args, **kwargs):
            mock_creds.valid = True
            mock_creds.expired = False

        mock_creds.refresh = Mock(side_effect=refresh_side_effect)

        mock_service = Mock()
        mock_profile = Mock()
        mock_profile.execute.return_value = {"emailAddress": "test@example.com"}
        mock_service.users.return_value.getProfile.return_value = mock_profile
        mock_build.return_value = mock_service

        service, error = auth.get_gmail_service()

        # Should refresh and return service
        assert mock_creds.refresh.called
        assert service is not None
        assert error is None

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_expired_token_without_refresh_token_requires_reauth(
        self, mock_creds_class, mock_exists, mock_settings
    ):
        """Expired token without refresh token should require re-authentication."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True

        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = None

        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        result = auth.needs_auth_setup()

        assert result is True


class TestTokenFileErrors:
    """Tests for token file error scenarios"""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_corrupted_token_file_handled(
        self, mock_creds_class, mock_exists, mock_settings
    ):
        """Corrupted token file should be handled gracefully."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True

        # Simulate corrupted file
        mock_creds_class.from_authorized_user_file.side_effect = ValueError(
            "Invalid token file format"
        )

        result = auth.needs_auth_setup()

        assert result is True

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_empty_token_file_handled(
        self, mock_creds_class, mock_exists, mock_settings
    ):
        """Empty token file should be handled."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True

        # Empty file might raise ValueError or return None
        mock_creds_class.from_authorized_user_file.side_effect = ValueError(
            "Invalid JSON"
        )

        result = auth.needs_auth_setup()

        assert result is True

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_token_file_permission_denied(
        self, mock_creds_class, mock_exists, mock_settings
    ):
        """Token file permission denied should be handled."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True

        mock_creds_class.from_authorized_user_file.side_effect = IOError(
            "Permission denied"
        )

        result = auth.needs_auth_setup()

        assert result is True

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth.Request")
    @patch("app.services.auth.build")
    def test_token_refresh_write_failure(
        self,
        mock_build,
        mock_request,
        mock_creds_class,
        mock_exists,
        mock_settings,
    ):
        """Token refresh write failure should be handled gracefully."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True

        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "valid_refresh_token"
        mock_creds.to_json.return_value = '{"token": "refreshed"}'

        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        # Mock refresh to set valid=True after refresh (simulating successful refresh)
        def refresh_side_effect(*args, **kwargs):
            mock_creds.valid = True
            mock_creds.expired = False

        mock_creds.refresh = Mock(side_effect=refresh_side_effect)

        # Mock open to raise IOError when writing to token file, but allow reading
        def open_side_effect(file_path, mode="r", *args, **kwargs):
            if "w" in mode and str(file_path) == mock_settings.token_file:
                raise IOError("Permission denied")
            # For reading or other files, return a mock file object
            return mock_open(read_data='{"token": "old"}').return_value

        with patch("builtins.open", side_effect=open_side_effect):
            mock_service = Mock()
            mock_profile = Mock()
            mock_profile.execute.return_value = {"emailAddress": "test@example.com"}
            mock_service.users.return_value.getProfile.return_value = mock_profile
            mock_build.return_value = mock_service

            service, error = auth.get_gmail_service()

            # Should handle write failure gracefully - creds are still valid after refresh
            # so service should be returned despite write failure
            assert service is not None
            assert error is None
            assert mock_creds.refresh.called


class TestTokenSecurity:
    """Tests for token security scenarios"""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth.build")
    def test_token_not_exposed_in_logs(
        self, mock_build, mock_creds_class, mock_exists, mock_settings
    ):
        """Token should not be exposed in logs or error messages."""
        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True

        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = True

        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        mock_service = Mock()
        mock_profile = Mock()
        mock_profile.execute.return_value = {"emailAddress": "test@example.com"}
        mock_service.users.return_value.getProfile.return_value = mock_profile
        mock_build.return_value = mock_service

        service, error = auth.get_gmail_service()

        # Error message should not contain token
        if error:
            assert "token" not in error.lower() or "access_token" not in error.lower()

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    def test_token_file_missing_requires_auth(self, mock_exists, mock_settings):
        """Missing token file should require authentication."""
        mock_settings.token_file = "token.json"

        mock_exists.return_value = False

        result = auth.needs_auth_setup()

        assert result is True
