"""
Tests for Actions API Endpoints
-------------------------------
Tests for POST action endpoints.
"""

from unittest.mock import patch

# client fixture is provided by conftest.py


class TestScanEndpoint:
    """Tests for POST /api/scan endpoint."""

    def test_scan_with_default_params(self, client):
        """POST /api/scan with default params should start scan."""
        response = client.post("/api/scan", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_scan_with_custom_limit(self, client):
        """POST /api/scan with custom limit should accept it."""
        response = client.post("/api/scan", json={"limit": 100})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_scan_with_filters(self, client):
        """POST /api/scan with filters should accept them."""
        response = client.post(
            "/api/scan",
            json={
                "limit": 500,
                "filters": {
                    "older_than": "30d",
                    "larger_than": "5M",
                    "category": "promotions",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_scan_with_invalid_limit(self, client):
        """POST /api/scan with invalid limit should fail validation."""
        response = client.post("/api/scan", json={"limit": 0})
        assert response.status_code == 422  # Validation error

    def test_scan_with_invalid_filters(self, client):
        """POST /api/scan with invalid filters should fail validation."""
        response = client.post("/api/scan", json={"filters": {"older_than": "invalid"}})
        assert response.status_code == 422  # Validation error


class TestAuthEndpoints:
    """Tests for auth-related endpoints."""

    @patch("app.api.actions.get_gmail_service")
    def test_sign_in(self, mock_get_service, client):
        """POST /api/sign-in should trigger sign-in flow."""
        # Mock to prevent actual OAuth flow and browser opening
        mock_get_service.return_value = (None, "Not authenticated")
        response = client.post("/api/sign-in")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "signing_in"

    @patch("app.api.actions.sign_out")
    def test_sign_out(self, mock_sign_out, client):
        """POST /api/sign-out should sign out user."""
        mock_sign_out.return_value = {"success": True}
        response = client.post("/api/sign-out")
        assert response.status_code == 200
        mock_sign_out.assert_called_once()


class TestUnsubscribeEndpoint:
    """Tests for POST /api/unsubscribe endpoint."""

    @patch("app.api.actions.unsubscribe_single")
    def test_unsubscribe_with_link(self, mock_unsubscribe, client):
        """POST /api/unsubscribe with link should process it."""
        mock_unsubscribe.return_value = {"success": True}
        response = client.post(
            "/api/unsubscribe",
            json={"domain": "example.com", "link": "https://example.com/unsubscribe"},
        )
        assert response.status_code == 200
        mock_unsubscribe.assert_called_once_with(
            "example.com", "https://example.com/unsubscribe"
        )

    def test_unsubscribe_with_empty_params(self, client):
        """POST /api/unsubscribe with empty params should accept defaults."""
        with patch("app.api.actions.unsubscribe_single") as mock:
            mock.return_value = {"success": False, "error": "No link provided"}
            response = client.post("/api/unsubscribe", json={})
            assert response.status_code == 200


class TestMarkReadEndpoint:
    """Tests for POST /api/mark-read endpoint."""

    def test_mark_read_with_default_params(self, client):
        """POST /api/mark-read with default params should start."""
        response = client.post("/api/mark-read", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_mark_read_with_custom_count(self, client):
        """POST /api/mark-read with custom count should accept it."""
        response = client.post("/api/mark-read", json={"count": 500})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_mark_read_with_filters(self, client):
        """POST /api/mark-read with filters should accept them."""
        response = client.post(
            "/api/mark-read",
            json={"count": 1000, "filters": {"category": "promotions"}},
        )
        assert response.status_code == 200

    def test_mark_read_exceeds_max_count(self, client):
        """POST /api/mark-read with count > 100000 should fail."""
        response = client.post("/api/mark-read", json={"count": 100001})
        assert response.status_code == 422


class TestDeleteScanEndpoint:
    """Tests for POST /api/delete-scan endpoint."""

    def test_delete_scan_with_default_params(self, client):
        """POST /api/delete-scan should start scan."""
        response = client.post("/api/delete-scan", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_delete_scan_with_filters(self, client):
        """POST /api/delete-scan with filters should accept them."""
        response = client.post(
            "/api/delete-scan", json={"limit": 1000, "filters": {"older_than": "90d"}}
        )
        assert response.status_code == 200


class TestDeleteEmailsEndpoint:
    """Tests for POST /api/delete-emails endpoint."""

    @patch("app.api.actions.delete_emails_by_sender")
    def test_delete_emails_by_sender(self, mock_delete, client):
        """POST /api/delete-emails should delete by sender."""
        mock_delete.return_value = {"success": True, "deleted": 10}
        response = client.post(
            "/api/delete-emails", json={"sender": "newsletter@example.com"}
        )
        assert response.status_code == 200
        mock_delete.assert_called_once_with("newsletter@example.com")


class TestDeleteBulkEndpoint:
    """Tests for POST /api/delete-emails-bulk endpoint."""

    @patch("app.api.actions.delete_emails_bulk_background")
    def test_delete_bulk_with_valid_senders(self, mock_delete, client):
        """POST /api/delete-emails-bulk with valid senders should start background task."""
        senders = ["sender1@example.com", "sender2@example.com"]
        response = client.post("/api/delete-emails-bulk", json={"senders": senders})
        assert response.status_code == 200
        assert response.json() == {"status": "started"}
        mock_delete.assert_called_once_with(senders)

    def test_delete_bulk_large_senders_list(self, client):
        """POST /api/delete-emails-bulk with many senders should succeed (no limit)."""
        senders = [f"sender{i}@example.com" for i in range(500)]
        response = client.post("/api/delete-emails-bulk", json={"senders": senders})
        assert response.status_code == 200
        assert response.json() == {"status": "started"}

    @patch("app.api.actions.delete_emails_bulk_background")
    def test_delete_bulk_with_empty_list(self, mock_delete, client):
        """POST /api/delete-emails-bulk with empty list should start background task."""
        response = client.post("/api/delete-emails-bulk", json={"senders": []})
        assert response.status_code == 200
        assert response.json() == {"status": "started"}
        mock_delete.assert_called_once_with([])


class TestRequestValidation:
    """Tests for request validation across endpoints."""

    def test_scan_missing_body(self, client):
        """POST /api/scan without body should use defaults."""
        response = client.post("/api/scan", json={})
        assert response.status_code == 200

    def test_invalid_json(self, client):
        """POST with invalid JSON should return 422."""
        response = client.post(
            "/api/scan",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_invalid_filter_category(self, client):
        """Invalid category filter should fail validation."""
        response = client.post(
            "/api/scan", json={"filters": {"category": "invalid_category"}}
        )
        assert response.status_code == 422

    def test_invalid_older_than_format(self, client):
        """Invalid older_than format should fail validation."""
        response = client.post("/api/scan", json={"filters": {"older_than": "30days"}})
        assert response.status_code == 422
