"""
Tests for Sign-In API Endpoints
--------------------------------
Tests for sign-in/sign-out API endpoints and authentication state management.
"""

from unittest.mock import Mock, patch


from app.core import state


class TestSignInAPIEndpoint:
    """Tests for POST /api/sign-in endpoint"""

    @patch("app.api.actions.get_gmail_service")
    def test_sign_in_endpoint_triggers_oauth(self, mock_get_service, client):
        """POST /api/sign-in should trigger OAuth flow in background."""
        # Mock to return "signing in" message
        mock_get_service.return_value = (
            None,
            "Sign-in started. Please complete authorization in your browser.",
        )

        response = client.post("/api/sign-in")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "signing_in"
        # Verify get_gmail_service was called (in background task)
        # Note: Background task execution is async, so we verify the endpoint response

    @patch("app.api.actions.get_gmail_service")
    def test_sign_in_endpoint_non_blocking(self, mock_get_service, client):
        """POST /api/sign-in should not block the request."""
        mock_get_service.return_value = (
            None,
            "Sign-in started. Please complete authorization in your browser.",
        )

        response = client.post("/api/sign-in")

        # Should return immediately
        assert response.status_code == 200
        assert response.json()["status"] == "signing_in"

    @patch("app.api.actions.get_gmail_service")
    def test_sign_in_when_already_in_progress(self, mock_get_service, client):
        """POST /api/sign-in when auth already in progress should return immediately."""
        mock_get_service.return_value = (
            None,
            "Sign-in already in progress. Please complete the authorization in your browser.",
        )

        response = client.post("/api/sign-in")

        assert response.status_code == 200
        assert response.json()["status"] == "signing_in"


class TestSignOutAPIEndpoint:
    """Tests for POST /api/sign-out endpoint"""

    @patch("app.api.actions.sign_out")
    def test_sign_out_endpoint_success(self, mock_sign_out, client):
        """POST /api/sign-out should sign out successfully."""
        mock_sign_out.return_value = {
            "success": True,
            "message": "Signed out successfully",
            "results_cleared": True,
        }

        response = client.post("/api/sign-out")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Signed out successfully"
        assert data["results_cleared"] is True
        mock_sign_out.assert_called_once()

    @patch("app.api.actions.sign_out")
    def test_sign_out_endpoint_error_handling(self, mock_sign_out, client):
        """POST /api/sign-out should handle errors gracefully."""
        # Simulate sign_out raising an exception
        mock_sign_out.side_effect = Exception("Failed to remove token file")

        response = client.post("/api/sign-out")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to sign out" in data["detail"]
        mock_sign_out.assert_called_once()

    @patch("app.api.actions.sign_out")
    def test_sign_out_when_not_logged_in(self, mock_sign_out, client):
        """POST /api/sign-out when not logged in should still succeed."""
        mock_sign_out.return_value = {
            "success": True,
            "message": "Signed out successfully",
            "results_cleared": False,
        }

        response = client.post("/api/sign-out")

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestAuthStatusAPIEndpoint:
    """Tests for GET /api/auth-status endpoint"""

    @patch("app.api.status.check_login_status")
    def test_auth_status_when_logged_in(self, mock_check_status, client):
        """GET /api/auth-status when logged in should return user info."""
        mock_check_status.return_value = {
            "email": "test@example.com",
            "logged_in": True,
        }

        response = client.get("/api/auth-status")

        assert response.status_code == 200
        data = response.json()
        assert data["logged_in"] is True
        assert data["email"] == "test@example.com"
        mock_check_status.assert_called_once()

    @patch("app.api.status.check_login_status")
    def test_auth_status_when_logged_out(self, mock_check_status, client):
        """GET /api/auth-status when logged out should return logged_out state."""
        mock_check_status.return_value = {
            "email": None,
            "logged_in": False,
        }

        response = client.get("/api/auth-status")

        assert response.status_code == 200
        data = response.json()
        assert data["logged_in"] is False
        assert data["email"] is None

    @patch("app.api.status.check_login_status")
    def test_auth_status_updates_state(self, mock_check_status, client):
        """GET /api/auth-status should update current_user state."""
        # Reset state
        state.current_user = {"email": None, "logged_in": False}

        mock_check_status.return_value = {
            "email": "updated@example.com",
            "logged_in": True,
        }

        response = client.get("/api/auth-status")

        assert response.status_code == 200
        # State should be updated by check_login_status
        mock_check_status.assert_called_once()


class TestWebAuthStatusAPIEndpoint:
    """Tests for GET /api/web-auth-status endpoint"""

    @patch("app.api.status.get_web_auth_status")
    def test_web_auth_status_with_credentials(self, mock_get_status, client):
        """GET /api/web-auth-status with credentials should return status."""
        mock_get_status.return_value = {
            "needs_setup": False,
            "web_auth_mode": True,
            "has_credentials": True,
            "pending_auth_url": None,
        }

        response = client.get("/api/web-auth-status")

        assert response.status_code == 200
        data = response.json()
        assert data["has_credentials"] is True
        assert data["web_auth_mode"] is True
        assert data["needs_setup"] is False

    @patch("app.api.status.get_web_auth_status")
    def test_web_auth_status_without_credentials(self, mock_get_status, client):
        """GET /api/web-auth-status without credentials should indicate setup needed."""
        mock_get_status.return_value = {
            "needs_setup": True,
            "web_auth_mode": False,
            "has_credentials": False,
            "pending_auth_url": None,
        }

        response = client.get("/api/web-auth-status")

        assert response.status_code == 200
        data = response.json()
        assert data["has_credentials"] is False
        assert data["needs_setup"] is True

    @patch("app.api.status.get_web_auth_status")
    def test_web_auth_status_with_pending_url(self, mock_get_status, client):
        """GET /api/web-auth-status with pending auth URL should return it."""
        mock_get_status.return_value = {
            "needs_setup": True,
            "web_auth_mode": True,
            "has_credentials": True,
            "pending_auth_url": "https://oauth.example.com/auth",
        }

        response = client.get("/api/web-auth-status")

        assert response.status_code == 200
        data = response.json()
        assert data["pending_auth_url"] == "https://oauth.example.com/auth"

    @patch("app.api.status.get_web_auth_status")
    def test_web_auth_status_web_auth_mode_missing_credentials(
        self, mock_get_status, client
    ):
        """GET /api/web-auth-status in web auth mode without credentials should indicate setup needed."""
        mock_get_status.return_value = {
            "needs_setup": True,
            "web_auth_mode": True,
            "has_credentials": False,
            "pending_auth_url": None,
        }

        response = client.get("/api/web-auth-status")

        assert response.status_code == 200
        data = response.json()
        assert data["web_auth_mode"] is True
        assert data["has_credentials"] is False
        assert data["needs_setup"] is True


class TestAuthenticationStatePersistence:
    """Tests for authentication state persistence scenarios"""

    @patch("app.services.auth.settings")
    @patch("app.services.auth._is_file_empty")
    @patch("app.services.auth.os.path.exists")
    @patch("app.services.auth.Credentials")
    @patch("app.services.auth.build")
    def test_auth_state_persists_after_restart(
        self,
        mock_build,
        mock_creds_class,
        mock_exists,
        mock_is_file_empty,
        mock_settings,
    ):
        """Authentication state should persist after application restart."""
        from app.services import auth

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True
        mock_is_file_empty.return_value = False

        mock_creds = Mock()
        mock_creds.valid = True

        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        mock_service = Mock()
        mock_profile = Mock()
        mock_profile.execute.return_value = {"emailAddress": "persisted@example.com"}
        mock_service.users.return_value.getProfile.return_value = mock_profile
        mock_build.return_value = mock_service

        # Reset state (simulating restart)
        state.current_user = {"email": None, "logged_in": False}

        result = auth.check_login_status()

        # Should restore state from token
        assert result["logged_in"] is True
        assert result["email"] == "persisted@example.com"

    @patch("app.services.auth.settings")
    @patch("os.path.exists")
    @patch("app.services.auth.Credentials")
    def test_auth_state_after_token_expiry(
        self, mock_creds_class, mock_exists, mock_settings
    ):
        """Authentication state should be cleared after token expiry without refresh."""
        from app.services import auth

        mock_settings.token_file = "token.json"
        mock_settings.scopes = ["scope1", "scope2"]

        mock_exists.return_value = True

        # Expired token without refresh token
        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = None

        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        state.current_user = {"email": "old@example.com", "logged_in": True}

        result = auth.check_login_status()

        # Should detect expired token and return logged out
        assert result["logged_in"] is False
        assert result["email"] is None
