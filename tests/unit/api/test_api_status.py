"""
Tests for Status API Endpoints
------------------------------
Tests for GET status endpoints.
"""

from unittest.mock import patch

# client fixture is provided by conftest.py


class TestStatusEndpoints:
    """Tests for /api/status endpoints."""

    def test_root_returns_html(self, client):
        """Root endpoint should return HTML page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_get_scan_status(self, client):
        """GET /api/status should return scan status."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        # Check expected fields exist
        assert "done" in data
        assert "message" in data

    def test_get_scan_results(self, client):
        """GET /api/results should return scan results."""
        response = client.get("/api/results")
        assert response.status_code == 200
        data = response.json()
        # Results is a list of sender objects
        assert isinstance(data, list)

    def test_get_auth_status(self, client):
        """GET /api/auth-status should return auth status."""
        response = client.get("/api/auth-status")
        assert response.status_code == 200
        data = response.json()
        assert "logged_in" in data

    def test_get_web_auth_status(self, client):
        """GET /api/web-auth-status should return web auth status."""
        response = client.get("/api/web-auth-status")
        assert response.status_code == 200
        data = response.json()
        # Check expected web auth fields
        assert "web_auth_mode" in data or "has_credentials" in data

    @patch("app.services.auth.get_gmail_service")
    def test_get_unread_count(self, mock_get_service, client):
        """GET /api/unread-count should return unread count."""
        # Mock get_gmail_service to return error (no auth) to prevent browser opening
        mock_get_service.return_value = (None, "Not authenticated")
        response = client.get("/api/unread-count")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data or "error" in data

    def test_get_mark_read_status(self, client):
        """GET /api/mark-read-status should return mark-read status."""
        response = client.get("/api/mark-read-status")
        assert response.status_code == 200
        data = response.json()
        assert "done" in data
        assert "message" in data

    def test_get_delete_scan_status(self, client):
        """GET /api/delete-scan-status should return delete scan status."""
        response = client.get("/api/delete-scan-status")
        assert response.status_code == 200
        data = response.json()
        assert "done" in data
        assert "message" in data

    def test_get_delete_scan_results(self, client):
        """GET /api/delete-scan-results should return delete scan results."""
        response = client.get("/api/delete-scan-results")
        assert response.status_code == 200
        data = response.json()
        # Results is a list of sender objects
        assert isinstance(data, list)


class TestDocsEndpoints:
    """Tests for API documentation endpoints."""

    def test_docs_endpoint(self, client):
        """GET /docs should return Swagger UI."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint(self, client):
        """GET /redoc should return ReDoc."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_schema(self, client):
        """GET /openapi.json should return OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
