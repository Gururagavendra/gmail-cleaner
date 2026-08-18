"""
Tests for Authentication Service
--------------------------------
Tests for auth.py - OAuth2 authentication with Gmail API.
"""

import json
import os
from unittest.mock import Mock, patch, mock_open, MagicMock

import pytest

from app.core import state


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.update_current_user(email=None, logged_in=False)
    yield
    state.update_current_user(email=None, logged_in=False)


@pytest.fixture
def reset_auth_progress():
    """Reset auth in progress flag."""
    from app.services import auth
    auth._auth_in_progress["active"] = False
    yield
    auth._auth_in_progress["active"] = False


class TestIsFileEmpty:
    """Tests for _is_file_empty function."""

    def test_file_not_exists(self):
        """Non-existent file should return False."""
        from app.services.auth import _is_file_empty

        result = _is_file_empty("/nonexistent/path/file.json")
        assert result is False

    @patch("builtins.open", mock_open(read_data=""))
    @patch("os.path.exists")
    def test_empty_file(self, mock_exists):
        """Empty file should return True."""
        from app.services.auth import _is_file_empty

        mock_exists.return_value = True
        result = _is_file_empty("empty.json")
        assert result is True

    @patch("builtins.open", mock_open(read_data="   \n  "))
    @patch("os.path.exists")
    def test_whitespace_only_file(self, mock_exists):
        """Whitespace-only file should return True."""
        from app.services.auth import _is_file_empty

        mock_exists.return_value = True
        result = _is_file_empty("whitespace.json")
        assert result is True

    @patch("builtins.open", mock_open(read_data='{"key": "value"}'))
    @patch("os.path.exists")
    def test_non_empty_file(self, mock_exists):
        """Non-empty file should return False."""
        from app.services.auth import _is_file_empty

        mock_exists.return_value = True
        result = _is_file_empty("content.json")
        assert result is False

    @patch("os.path.exists")
    def test_read_error(self, mock_exists):
        """OSError during read should return False."""
        from app.services.auth import _is_file_empty

        mock_exists.return_value = True
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = _is_file_empty("unreadable.json")
        assert result is False


class TestIsWebAuthMode:
    """Tests for is_web_auth_mode function."""

    @patch("app.services.auth.settings")
    def test_web_auth_enabled(self, mock_settings):
        """Should return True when web_auth is enabled."""
        from app.services.auth import is_web_auth_mode

        mock_settings.web_auth = True
        assert is_web_auth_mode() is True

    @patch("app.services.auth.settings")
    def test_web_auth_disabled(self, mock_settings):
        """Should return False when web_auth is disabled."""
        from app.services.auth import is_web_auth_mode

        mock_settings.web_auth = False
        assert is_web_auth_mode() is False


class TestNeedsAuthSetup:
    """Tests for needs_auth_setup function."""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    def test_no_token_file(self, mock_exists, mock_settings):
        """No token file should return True."""
        from app.services.auth import needs_auth_setup

        mock_settings.token_file = "token.json"
        mock_exists.return_value = False

        assert needs_auth_setup() is True

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_empty_token_file(self, mock_remove, mock_exists, mock_is_empty, mock_settings):
        """Empty token file should return True and be removed."""
        from app.services.auth import needs_auth_setup

        mock_settings.token_file = "token.json"
        mock_exists.return_value = True
        mock_is_empty.return_value = True

        assert needs_auth_setup() is True
        mock_remove.assert_called_once_with("token.json")

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_valid_credentials(self, mock_creds_class, mock_exists, mock_is_empty, mock_settings):
        """Valid credentials should return False."""
        from app.services.auth import needs_auth_setup

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        mock_creds = Mock()
        mock_creds.valid = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        assert needs_auth_setup() is False

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_expired_with_refresh_token(self, mock_creds_class, mock_exists, mock_is_empty, mock_settings):
        """Expired credentials with refresh token should return False."""
        from app.services.auth import needs_auth_setup

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.refresh_token = "refresh_token"
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        assert needs_auth_setup() is False

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_corrupted_token_file(self, mock_creds_class, mock_exists, mock_is_empty, mock_settings):
        """Corrupted token file should return True."""
        from app.services.auth import needs_auth_setup

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        mock_creds_class.from_authorized_user_file.side_effect = ValueError("Invalid JSON")

        assert needs_auth_setup() is True


class TestGetWebAuthStatus:
    """Tests for get_web_auth_status function."""

    @patch("app.services.auth.needs_auth_setup")
    @patch("app.services.auth.is_web_auth_mode")
    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    def test_returns_status_dict(self, mock_exists, mock_settings, mock_web_mode, mock_needs_setup):
        """Should return complete status dictionary."""
        from app.services.auth import get_web_auth_status

        mock_needs_setup.return_value = False
        mock_web_mode.return_value = True
        mock_settings.credentials_file = "credentials.json"
        mock_exists.return_value = True
        state.set_pending_auth_url("https://oauth.example.com")

        result = get_web_auth_status()

        assert result["needs_setup"] is False
        assert result["web_auth_mode"] is True
        assert result["has_credentials"] is True
        assert result["pending_auth_url"] == "https://oauth.example.com"


class TestTryRefreshCreds:
    """Tests for _try_refresh_creds function."""

    @patch("app.services.auth.settings")
    @patch("app.services.auth.Request")
    def test_successful_refresh(self, mock_request, mock_settings):
        """Successful refresh should return refreshed credentials."""
        from app.services.auth import _try_refresh_creds

        mock_settings.token_file = "token.json"

        mock_creds = Mock()
        mock_creds.to_json.return_value = '{"token": "new_token"}'

        with patch("builtins.open", mock_open()):
            result = _try_refresh_creds(mock_creds)

        assert result == mock_creds
        mock_creds.refresh.assert_called_once()

    @patch("app.services.auth.settings")
    @patch("app.services.auth.Request")
    @patch("os.remove")
    def test_refresh_error(self, mock_remove, mock_request, mock_settings):
        """RefreshError should return None and remove token file."""
        from app.services.auth import _try_refresh_creds
        from google.auth.exceptions import RefreshError

        mock_settings.token_file = "token.json"

        mock_creds = Mock()
        mock_creds.refresh.side_effect = RefreshError("Token expired")

        result = _try_refresh_creds(mock_creds)

        assert result is None
        mock_remove.assert_called_once_with("token.json")

    @patch("app.services.auth.settings")
    @patch("app.services.auth.Request")
    def test_token_save_error(self, mock_request, mock_settings):
        """OSError during save should still return refreshed credentials."""
        from app.services.auth import _try_refresh_creds

        mock_settings.token_file = "token.json"

        mock_creds = Mock()
        mock_creds.to_json.return_value = '{"token": "new_token"}'

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = _try_refresh_creds(mock_creds)

        # Credentials refreshed in memory even if save failed
        assert result == mock_creds


class TestGetCredentialsPath:
    """Tests for _get_credentials_path function."""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    def test_credentials_file_exists(self, mock_exists, mock_settings):
        """Existing valid credentials file should return path."""
        from app.services.auth import _get_credentials_path

        mock_settings.credentials_file = "credentials.json"
        mock_exists.return_value = True

        with patch("builtins.open", mock_open(read_data='{"client_id": "test"}')):
            result = _get_credentials_path()

        assert result == "credentials.json"

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    def test_empty_credentials_file(self, mock_exists, mock_is_empty, mock_settings):
        """Empty credentials file should return None."""
        from app.services.auth import _get_credentials_path

        mock_settings.credentials_file = "credentials.json"
        mock_exists.return_value = True
        mock_is_empty.return_value = True

        result = _get_credentials_path()

        assert result is None

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    def test_invalid_json_credentials(self, mock_exists, mock_is_empty, mock_settings):
        """Invalid JSON in credentials should return None."""
        from app.services.auth import _get_credentials_path

        mock_settings.credentials_file = "credentials.json"
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        with patch("builtins.open", mock_open(read_data="not valid json")):
            result = _get_credentials_path()

        assert result is None

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("os.environ.get")
    def test_credentials_from_env_var(self, mock_env_get, mock_exists, mock_settings):
        """Should create credentials file from env var."""
        from app.services.auth import _get_credentials_path

        mock_settings.credentials_file = "credentials.json"
        mock_exists.return_value = False
        mock_env_get.return_value = '{"client_id": "from_env"}'

        with patch("builtins.open", mock_open()):
            result = _get_credentials_path()

        assert result == "credentials.json"

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("os.environ.get")
    def test_invalid_env_var_json(self, mock_env_get, mock_exists, mock_settings):
        """Invalid JSON in env var should return None."""
        from app.services.auth import _get_credentials_path

        mock_settings.credentials_file = "credentials.json"
        mock_exists.return_value = False
        mock_env_get.return_value = "not valid json"

        result = _get_credentials_path()

        assert result is None

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("os.environ.get")
    def test_no_credentials_available(self, mock_env_get, mock_exists, mock_settings):
        """No credentials available should return None."""
        from app.services.auth import _get_credentials_path

        mock_settings.credentials_file = "credentials.json"
        mock_exists.return_value = False
        mock_env_get.return_value = None

        result = _get_credentials_path()

        assert result is None


class TestGetGmailService:
    """Tests for get_gmail_service function."""

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth.build")
    def test_valid_credentials(self, mock_build, mock_creds_class, mock_exists, mock_is_empty, mock_settings):
        """Valid credentials should return service."""
        from app.services.auth import get_gmail_service

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        mock_creds = Mock()
        mock_creds.valid = True
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        mock_service = Mock()
        mock_profile = Mock()
        mock_profile.execute.return_value = {"emailAddress": "test@example.com"}
        mock_service.users.return_value.getProfile.return_value = mock_profile
        mock_build.return_value = mock_service

        service, error = get_gmail_service()

        assert service is not None
        assert error is None

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth._get_credentials_path")
    def test_no_credentials(self, mock_get_creds_path, mock_exists, mock_is_empty, mock_settings, reset_auth_progress):
        """Missing credentials should return error."""
        from app.services.auth import get_gmail_service

        mock_settings.token_file = "token.json"
        mock_settings.credentials_file = "credentials.json"
        mock_exists.return_value = False
        mock_is_empty.return_value = False
        mock_get_creds_path.return_value = None

        service, error = get_gmail_service()

        assert service is None
        assert "credentials.json" in error

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth._try_refresh_creds")
    @patch("app.services.auth.build")
    def test_expired_credentials_refreshed(
        self, mock_build, mock_refresh, mock_creds_class, mock_exists, mock_is_empty, mock_settings
    ):
        """Expired credentials should be refreshed."""
        from app.services.auth import get_gmail_service

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        # First call returns expired creds
        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        # Refresh returns valid creds
        mock_refreshed_creds = Mock()
        mock_refreshed_creds.valid = True
        mock_refresh.return_value = mock_refreshed_creds

        mock_service = Mock()
        mock_profile = Mock()
        mock_profile.execute.return_value = {"emailAddress": "test@example.com"}
        mock_service.users.return_value.getProfile.return_value = mock_profile
        mock_build.return_value = mock_service

        service, error = get_gmail_service()

        assert service is not None
        assert error is None
        mock_refresh.assert_called_once_with(mock_creds)

    @patch("app.services.auth._auth_in_progress", {"active": True})
    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    def test_auth_already_in_progress(self, mock_exists, mock_settings):
        """Auth already in progress should return message."""
        from app.services.auth import get_gmail_service

        mock_settings.token_file = "token.json"
        mock_exists.return_value = False

        service, error = get_gmail_service()

        assert service is None
        assert "already in progress" in error

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth.build")
    def test_build_service_error(self, mock_build, mock_creds_class, mock_exists, mock_is_empty, mock_settings):
        """Build service error should return error message."""
        from app.services.auth import get_gmail_service

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        mock_creds = Mock()
        mock_creds.valid = True
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        mock_build.side_effect = Exception("API connection failed")

        service, error = get_gmail_service()

        assert service is None
        assert "Failed to connect" in error


class TestSignOut:
    """Tests for sign_out function."""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_sign_out_removes_token(self, mock_remove, mock_exists, mock_settings):
        """Sign out should remove token file."""
        from app.services.auth import sign_out

        mock_settings.token_file = "token.json"
        mock_exists.return_value = True

        result = sign_out()

        assert result["success"] is True
        mock_remove.assert_called_once_with("token.json")

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    def test_sign_out_no_token_file(self, mock_exists, mock_settings):
        """Sign out when no token file should still succeed."""
        from app.services.auth import sign_out

        mock_settings.token_file = "token.json"
        mock_exists.return_value = False

        result = sign_out()

        assert result["success"] is True

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_sign_out_resets_state(self, mock_remove, mock_exists, mock_settings):
        """Sign out should reset application state."""
        from app.services.auth import sign_out

        mock_settings.token_file = "token.json"
        mock_exists.return_value = True

        # Set some state
        state.update_current_user(email="test@example.com", logged_in=True)

        result = sign_out()

        assert result["success"] is True
        assert result["results_cleared"] is True


class TestCheckLoginStatus:
    """Tests for check_login_status function."""

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    def test_no_token_file(self, mock_exists, mock_settings):
        """No token file should return logged out."""
        from app.services.auth import check_login_status

        mock_settings.token_file = "token.json"
        mock_exists.return_value = False

        result = check_login_status()

        assert result["logged_in"] is False
        assert result["email"] is None

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_empty_token_file(self, mock_remove, mock_exists, mock_is_empty, mock_settings):
        """Empty token file should return logged out and be removed."""
        from app.services.auth import check_login_status

        mock_settings.token_file = "token.json"
        mock_exists.return_value = True
        mock_is_empty.return_value = True

        result = check_login_status()

        assert result["logged_in"] is False
        mock_remove.assert_called_once()

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth.build")
    def test_valid_credentials(self, mock_build, mock_creds_class, mock_exists, mock_is_empty, mock_settings):
        """Valid credentials should return logged in with email."""
        from app.services.auth import check_login_status

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        mock_creds = Mock()
        mock_creds.valid = True
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        mock_service = Mock()
        mock_profile = Mock()
        mock_profile.execute.return_value = {"emailAddress": "user@example.com"}
        mock_service.users.return_value.getProfile.return_value = mock_profile
        mock_build.return_value = mock_service

        result = check_login_status()

        assert result["logged_in"] is True
        assert result["email"] == "user@example.com"

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth._try_refresh_creds")
    @patch("app.services.auth.build")
    def test_expired_credentials_refreshed(
        self, mock_build, mock_refresh, mock_creds_class, mock_exists, mock_is_empty, mock_settings
    ):
        """Expired credentials should be refreshed."""
        from app.services.auth import check_login_status

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        mock_refreshed_creds = Mock()
        mock_refresh.return_value = mock_refreshed_creds

        mock_service = Mock()
        mock_profile = Mock()
        mock_profile.execute.return_value = {"emailAddress": "refreshed@example.com"}
        mock_service.users.return_value.getProfile.return_value = mock_profile
        mock_build.return_value = mock_service

        result = check_login_status()

        assert result["logged_in"] is True
        assert result["email"] == "refreshed@example.com"
        mock_refresh.assert_called_once()

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("os.remove")
    def test_corrupted_token_file(self, mock_remove, mock_creds_class, mock_exists, mock_is_empty, mock_settings):
        """Corrupted token file should return logged out and be removed."""
        from app.services.auth import check_login_status

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        mock_creds_class.from_authorized_user_file.side_effect = ValueError("Invalid JSON")

        result = check_login_status()

        assert result["logged_in"] is False
        mock_remove.assert_called_once()

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth.build")
    def test_api_error(self, mock_build, mock_creds_class, mock_exists, mock_is_empty, mock_settings):
        """API error should return logged out."""
        from app.services.auth import check_login_status

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1"]
        mock_exists.return_value = True
        mock_is_empty.return_value = False

        mock_creds = Mock()
        mock_creds.valid = True
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        mock_build.side_effect = Exception("API unavailable")

        result = check_login_status()

        assert result["logged_in"] is False
