"""
Tests for Gmail Delete Operations
---------------------------------
Tests for delete.py - scanning senders and deleting emails.
"""

from unittest.mock import Mock, patch, MagicMock

import pytest

from app.core import state
from app.services.gmail.delete import (
    scan_senders_for_delete,
    get_delete_scan_status,
    get_delete_scan_results,
    delete_emails_by_sender,
    delete_emails_bulk,
    delete_emails_bulk_background,
    get_delete_bulk_status,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.reset_delete_scan()
    state.reset_delete_bulk()
    yield
    state.reset_delete_scan()
    state.reset_delete_bulk()


class TestScanSendersForDelete:
    """Tests for scan_senders_for_delete function."""

    def test_invalid_limit_zero(self):
        """Zero limit should set error and return early."""
        scan_senders_for_delete(limit=0)
        status = get_delete_scan_status()
        assert status["error"] == "Limit must be greater than 0"
        assert status["done"] is True

    def test_invalid_limit_negative(self):
        """Negative limit should set error and return early."""
        scan_senders_for_delete(limit=-10)
        status = get_delete_scan_status()
        assert status["error"] == "Limit must be greater than 0"
        assert status["done"] is True

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication failed")

        scan_senders_for_delete(limit=100)

        status = get_delete_scan_status()
        assert status["error"] == "Authentication failed"
        assert status["done"] is True

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_no_emails_found(self, mock_get_service):
        """Empty result should set appropriate message."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Mock the chained API calls
        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = mock_list

        scan_senders_for_delete(limit=100)

        status = get_delete_scan_status()
        assert status["message"] == "No emails found"
        assert status["done"] is True
        assert status["error"] is None

    @patch("app.services.gmail.delete.get_gmail_service")
    @patch("app.services.gmail.delete.time.sleep")
    def test_successful_scan(self, _mock_sleep, mock_get_service):
        """Successful scan should return grouped senders with correct counts."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Mock list to return message IDs
        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}, {"id": "msg3"}]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = mock_list

        # Prepare mock message responses - 2 from sender1, 1 from sender2
        mock_messages = [
            {
                "id": "msg1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "sender1@example.com"},
                        {"name": "Subject", "value": "Subject 1"},
                        {"name": "Date", "value": "Mon, 01 Jan 2024 10:00:00 +0000"},
                    ]
                },
                "sizeEstimate": 1000,
            },
            {
                "id": "msg2",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "sender1@example.com"},
                        {"name": "Subject", "value": "Subject 2"},
                        {"name": "Date", "value": "Tue, 02 Jan 2024 10:00:00 +0000"},
                    ]
                },
                "sizeEstimate": 2000,
            },
            {
                "id": "msg3",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "sender2@example.com"},
                        {"name": "Subject", "value": "Subject 3"},
                        {"name": "Date", "value": "Wed, 03 Jan 2024 10:00:00 +0000"},
                    ]
                },
                "sizeEstimate": 500,
            },
        ]

        # Mock batch request to invoke callback with each message
        def mock_new_batch(callback):
            batch = Mock()
            batch.add = Mock()

            def execute_batch():
                for i, msg in enumerate(mock_messages):
                    callback(str(i), msg, None)

            batch.execute = execute_batch
            return batch

        mock_service.new_batch_http_request = mock_new_batch

        scan_senders_for_delete(limit=10)

        status = get_delete_scan_status()
        assert status["done"] is True
        assert status["error"] is None

        # Verify scan results
        results = get_delete_scan_results()
        assert len(results) == 2  # 2 unique senders

        # Results should be sorted by count (descending)
        assert results[0]["email"] == "sender1@example.com"
        assert results[0]["count"] == 2
        assert results[0]["total_size"] == 3000  # 1000 + 2000

        assert results[1]["email"] == "sender2@example.com"
        assert results[1]["count"] == 1
        assert results[1]["total_size"] == 500

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_exception_handling(self, mock_get_service):
        """Exceptions should be caught and set error status."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Mock list to raise exception
        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception("API Error")

        scan_senders_for_delete(limit=100)

        status = get_delete_scan_status()
        assert status["error"] == "API Error"
        assert status["done"] is True


class TestDeleteEmailsBySender:
    """Tests for delete_emails_by_sender function."""

    def test_empty_sender(self):
        """Empty sender should return error."""
        result = delete_emails_by_sender("")
        assert result["success"] is False
        assert result["message"] == "No sender specified"

    def test_whitespace_sender(self):
        """Whitespace-only sender should return error."""
        result = delete_emails_by_sender("   ")
        assert result["success"] is False
        assert result["message"] == "No sender specified"

    def test_invalid_sender_format(self):
        """Invalid sender format should return error."""
        result = delete_emails_by_sender("not-an-email")
        assert result["success"] is False
        assert "Invalid sender format" in result["message"]

    def test_invalid_sender_with_operators(self):
        """Sender with query operators should be rejected (unless quoted)."""
        # This tests our input validation - the value itself is validated before use
        result = delete_emails_by_sender("test OR admin@example.com")
        assert result["success"] is False
        assert "Invalid sender format" in result["message"]

    def test_valid_email_format_no_scan_results(self):
        """Valid email without scan results should fail with message."""
        result = delete_emails_by_sender("user@example.com")
        assert result["success"] is False
        assert "scan" in result["message"].lower()

    def test_valid_email_format_empty_message_ids(self):
        """Valid email with empty message_ids should return no emails found."""
        # Set up scan results with empty message_ids
        state.set_delete_scan_results([{
            "email": "user@example.com",
            "message_ids": [],
            "count": 0,
            "total_size": 0,
        }])

        result = delete_emails_by_sender("user@example.com")
        assert result["success"] is True
        assert result["message"] == "No emails found"

    def test_valid_domain_format_no_scan_results(self):
        """Valid domain without scan results should fail with message."""
        result = delete_emails_by_sender("example.com")
        assert result["success"] is False
        assert "scan" in result["message"].lower()

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should return failure."""
        mock_get_service.return_value = (None, "Auth failed")

        # Set up scan results first
        state.set_delete_scan_results([{
            "email": "user@example.com",
            "message_ids": ["msg1", "msg2"],
            "count": 2,
            "total_size": 1000,
        }])

        result = delete_emails_by_sender("user@example.com")

        assert result["success"] is False
        assert result["message"] == "Auth failed"

    def test_no_scan_results(self):
        """No scan results should return failure with message."""
        result = delete_emails_by_sender("sender@example.com")

        assert result["success"] is False
        assert "scan" in result["message"].lower()

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_successful_delete(self, mock_get_service):
        """Successful delete should return correct count using cached message_ids."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Set up scan results with message_ids
        state.set_delete_scan_results([{
            "email": "sender@example.com",
            "message_ids": [f"msg{i}" for i in range(5)],
            "count": 5,
            "total_size": 5000,
        }])

        # Mock batch modify
        mock_service.users.return_value.messages.return_value.batchModify.return_value.execute.return_value = {}

        result = delete_emails_by_sender("sender@example.com")

        assert result["success"] is True
        assert result["deleted"] == 5
        assert "Moved 5 emails to trash" in result["message"]

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_delete_with_many_messages(self, mock_get_service):
        """Delete should handle batching of many cached message_ids."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Set up scan results with 150 message_ids (more than batch size of 100)
        state.set_delete_scan_results([{
            "email": "sender@example.com",
            "message_ids": [f"msg{i}" for i in range(150)],
            "count": 150,
            "total_size": 150000,
        }])

        # Mock batch modify
        mock_service.users.return_value.messages.return_value.batchModify.return_value.execute.return_value = {}

        result = delete_emails_by_sender("sender@example.com")

        assert result["success"] is True
        assert result["deleted"] == 150

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_delete_updates_cached_results(self, mock_get_service):
        """Delete should remove sender from cached results."""
        # Set up cached results with message_ids
        state.set_delete_scan_results([
            {"email": "keep@example.com", "count": 5, "message_ids": ["k1", "k2"], "total_size": 500},
            {"email": "delete@example.com", "count": 10, "message_ids": ["d1", "d2"], "total_size": 1000},
        ])

        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)
        mock_service.users.return_value.messages.return_value.batchModify.return_value.execute.return_value = {}

        delete_emails_by_sender("delete@example.com")

        results = get_delete_scan_results()
        assert len(results) == 1
        assert results[0]["email"] == "keep@example.com"

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_exception_handling(self, mock_get_service):
        """Exceptions should be caught and returned as error."""
        # Set up scan results first
        state.set_delete_scan_results([{
            "email": "sender@example.com",
            "message_ids": ["msg1", "msg2"],
            "count": 2,
            "total_size": 1000,
        }])

        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)
        mock_service.users.return_value.messages.return_value.batchModify.return_value.execute.side_effect = Exception("API Error")

        result = delete_emails_by_sender("sender@example.com")

        assert result["success"] is False
        assert result["message"] == "API Error"


class TestDeleteEmailsBulk:
    """Tests for delete_emails_bulk function."""

    def test_empty_senders_list(self):
        """Empty senders list should return error."""
        result = delete_emails_bulk([])
        assert result["success"] is False
        assert result["message"] == "No senders specified"

    @patch("app.services.gmail.delete.delete_emails_by_sender")
    def test_all_successful(self, mock_delete):
        """All successful deletes should return combined counts."""
        mock_delete.side_effect = [
            {"success": True, "deleted": 5, "size_freed": 1000, "message": "ok"},
            {"success": True, "deleted": 10, "size_freed": 2000, "message": "ok"},
        ]

        result = delete_emails_bulk(["sender1@example.com", "sender2@example.com"])

        assert result["success"] is True
        assert result["deleted"] == 15
        assert result["size_freed"] == 3000

    @patch("app.services.gmail.delete.delete_emails_by_sender")
    def test_partial_failure(self, mock_delete):
        """Partial failure should report errors but still count successes."""
        mock_delete.side_effect = [
            {"success": True, "deleted": 5, "size_freed": 1000, "message": "ok"},
            {"success": False, "deleted": 0, "size_freed": 0, "message": "Auth error"},
        ]

        result = delete_emails_bulk(["sender1@example.com", "sender2@example.com"])

        assert result["success"] is True  # At least one succeeded
        assert result["deleted"] == 5
        assert "Errors:" in result["message"]

    @patch("app.services.gmail.delete.delete_emails_by_sender")
    def test_all_failed(self, mock_delete):
        """All failures should report total failure."""
        mock_delete.side_effect = [
            {"success": False, "deleted": 0, "size_freed": 0, "message": "Error 1"},
            {"success": False, "deleted": 0, "size_freed": 0, "message": "Error 2"},
        ]

        result = delete_emails_bulk(["sender1@example.com", "sender2@example.com"])

        assert result["success"] is False
        assert result["deleted"] == 0

    @patch("app.services.gmail.delete.delete_emails_by_sender")
    def test_no_emails_found_for_any(self, mock_delete):
        """No emails found for any sender should report appropriately."""
        mock_delete.side_effect = [
            {"success": True, "deleted": 0, "size_freed": 0, "message": "No emails"},
            {"success": True, "deleted": 0, "size_freed": 0, "message": "No emails"},
        ]

        result = delete_emails_bulk(["sender1@example.com", "sender2@example.com"])

        assert result["success"] is False
        assert result["message"] == "No emails found to delete"


class TestDeleteEmailsBulkBackground:
    """Tests for delete_emails_bulk_background function."""

    def test_empty_senders_list(self):
        """Empty senders list should set error status."""
        delete_emails_bulk_background([])

        status = get_delete_bulk_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_none_senders(self):
        """None senders should set error status."""
        delete_emails_bulk_background(None)

        status = get_delete_bulk_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_invalid_senders_type(self):
        """Invalid senders type should set error status."""
        delete_emails_bulk_background("not-a-list")

        status = get_delete_bulk_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Auth failed")

        delete_emails_bulk_background(["sender@example.com"])

        status = get_delete_bulk_status()
        assert status["error"] == "Auth failed"
        assert status["done"] is True

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_no_emails_found(self, mock_get_service):
        """No emails found (no scan results) should complete without error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # No scan results for this sender
        state.set_delete_scan_results([])

        delete_emails_bulk_background(["sender@example.com"])

        status = get_delete_bulk_status()
        assert status["done"] is True
        assert status["message"] == "No emails found to delete"
        assert status["progress"] == 100

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_successful_bulk_delete(self, mock_get_service):
        """Successful bulk delete should update status correctly using cached message_ids."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Set up scan results with message_ids
        state.set_delete_scan_results([{
            "email": "sender@example.com",
            "message_ids": [f"msg{i}" for i in range(10)],
            "count": 10,
            "total_size": 10000,
        }])

        # Mock batch modify
        mock_service.users.return_value.messages.return_value.batchModify.return_value.execute.return_value = {}

        delete_emails_bulk_background(["sender@example.com"])

        status = get_delete_bulk_status()
        assert status["done"] is True
        assert status["deleted_count"] == 10
        assert status["progress"] == 100
        assert "Successfully deleted" in status["message"]

    @patch("app.services.gmail.delete.get_gmail_service")
    def test_updates_cached_results(self, mock_get_service):
        """Bulk delete should remove senders from cached results."""
        state.set_delete_scan_results([
            {"email": "keep@example.com", "count": 5, "message_ids": ["k1"], "total_size": 500},
            {"email": "delete@example.com", "count": 10, "message_ids": ["d1", "d2"], "total_size": 1000},
        ])

        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)
        mock_service.users.return_value.messages.return_value.batchModify.return_value.execute.return_value = {}

        delete_emails_bulk_background(["delete@example.com"])

        results = get_delete_scan_results()
        assert len(results) == 1
        assert results[0]["email"] == "keep@example.com"


class TestStatusFunctions:
    """Tests for status retrieval functions."""

    def test_get_delete_scan_status_returns_copy(self):
        """get_delete_scan_status should return a copy."""
        state.update_delete_scan_status(message="Test")
        status1 = get_delete_scan_status()
        status2 = get_delete_scan_status()

        status1["message"] = "Modified"
        assert status2["message"] == "Test"

    def test_get_delete_scan_results_returns_copy(self):
        """get_delete_scan_results should return a copy."""
        state.set_delete_scan_results([{"email": "test@example.com"}])
        results1 = get_delete_scan_results()
        results2 = get_delete_scan_results()

        results1.append({"email": "new@example.com"})
        assert len(results2) == 1

    def test_get_delete_bulk_status_returns_copy(self):
        """get_delete_bulk_status should return a copy."""
        state.update_delete_bulk_status(message="Test")
        status1 = get_delete_bulk_status()
        status2 = get_delete_bulk_status()

        status1["message"] = "Modified"
        assert status2["message"] == "Test"
