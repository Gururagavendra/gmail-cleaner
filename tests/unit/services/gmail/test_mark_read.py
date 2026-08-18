"""
Tests for Gmail Mark Read Operations
------------------------------------
Tests for mark_read.py - marking emails as read.
"""

from unittest.mock import Mock, patch

import pytest

from app.core import state
from app.services.gmail.mark_read import (
    get_unread_count,
    mark_emails_as_read,
    get_mark_read_status,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.reset_mark_read()
    yield
    state.reset_mark_read()


class TestGetUnreadCount:
    """Tests for get_unread_count function."""

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_auth_error_returns_zero_count(self, mock_get_service):
        """Auth error should return count 0 with error message."""
        mock_get_service.return_value = (None, "Authentication required")

        result = get_unread_count()

        assert result["count"] == 0
        assert result["error"] == "Authentication required"

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_successful_count(self, mock_get_service):
        """Successful call should return estimated count."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"resultSizeEstimate": 42}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        result = get_unread_count()

        assert result["count"] == 42
        assert "error" not in result

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_empty_result(self, mock_get_service):
        """Empty result should return 0."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        result = get_unread_count()

        assert result["count"] == 0

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_api_exception(self, mock_get_service):
        """API exception should return 0 with error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception(
            "API Error"
        )

        result = get_unread_count()

        assert result["count"] == 0
        assert result["error"] == "API Error"


class TestMarkEmailsAsRead:
    """Tests for mark_emails_as_read function."""

    def test_negative_count_sets_error(self):
        """Negative count should set error and return early."""
        mark_emails_as_read(count=-5)

        status = get_mark_read_status()
        assert status["error"] == "Count must be 0 or greater"
        assert status["done"] is True

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        mark_emails_as_read(count=100)

        status = get_mark_read_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_no_unread_emails(self, mock_get_service):
        """No unread emails should set appropriate message."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mark_emails_as_read(count=100)

        status = get_mark_read_status()
        assert status["message"] == "No unread emails found"
        assert status["done"] is True
        assert status["progress"] == 100

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_successful_mark_read(self, mock_get_service):
        """Successful marking should update status and count."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Return 5 messages
        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(5)]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        # Mock batchModify
        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        mark_emails_as_read(count=10)

        status = get_mark_read_status()
        assert status["done"] is True
        assert status["error"] is None
        assert "Done! Marked 5 emails as read" in status["message"]

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_mark_all_with_zero_count(self, mock_get_service):
        """Count=0 should mark all unread emails."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Return messages across two pages
        call_count = [0]

        def list_execute():
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "messages": [{"id": f"msg{i}"} for i in range(100)],
                    "nextPageToken": "token1",
                }
            else:
                return {"messages": [{"id": f"msg{i}"} for i in range(100, 150)]}

        mock_list = Mock()
        mock_list.execute.side_effect = list_execute
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        mark_emails_as_read(count=0)

        status = get_mark_read_status()
        assert status["done"] is True
        # Should have marked all 150 emails
        assert "150" in status["message"]

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_respects_count_limit(self, mock_get_service):
        """Should only mark up to the specified count."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Return more messages than requested
        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(50)]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        mark_emails_as_read(count=10)

        status = get_mark_read_status()
        assert status["done"] is True
        assert "10" in status["message"]

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_with_filters(self, mock_get_service):
        """Should apply filters to query."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mark_emails_as_read(count=100, filters={"older_than": "30d"})

        # Verify query contains filter
        call_args = mock_service.users.return_value.messages.return_value.list.call_args
        assert "q" in call_args.kwargs
        query = call_args.kwargs["q"]
        assert "is:unread" in query
        assert "older_than:30d" in query

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_exception_handling(self, mock_get_service):
        """Exceptions should be caught and set error status."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception(
            "API Error"
        )

        mark_emails_as_read(count=100)

        status = get_mark_read_status()
        assert status["error"] == "API Error"
        assert status["done"] is True

    @patch("app.services.gmail.mark_read.get_gmail_service")
    def test_batch_processing(self, mock_get_service):
        """Should process in batches of 100."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Return 250 messages
        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(250)]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        mark_emails_as_read(count=250)

        # Should have called batchModify 3 times (100 + 100 + 50)
        assert mock_service.users.return_value.messages.return_value.batchModify.call_count == 3


class TestGetMarkReadStatus:
    """Tests for get_mark_read_status function."""

    def test_returns_copy(self):
        """get_mark_read_status should return a copy."""
        state.update_mark_read_status(message="Test")
        status1 = get_mark_read_status()
        status2 = get_mark_read_status()

        status1["message"] = "Modified"
        assert status2["message"] == "Test"
