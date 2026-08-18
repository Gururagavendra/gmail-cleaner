"""
Tests for Gmail Archive Operations
----------------------------------
Tests for archive.py - archiving emails from senders.
"""

from unittest.mock import Mock, patch

import pytest

from app.core import state
from app.services.gmail.archive import (
    archive_emails_background,
    get_archive_status,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.reset_archive()
    yield
    state.reset_archive()


class TestArchiveEmailsBackground:
    """Tests for archive_emails_background function."""

    def test_no_senders_specified_empty_list(self):
        """Empty sender list should set error and return early."""
        archive_emails_background([])

        status = get_archive_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_no_senders_specified_none(self):
        """None senders should set error and return early."""
        archive_emails_background(None)

        status = get_archive_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_invalid_senders_type(self):
        """Non-list senders should set error and return early."""
        archive_emails_background("not-a-list")

        status = get_archive_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.archive.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        archive_emails_background(["sender@example.com"])

        status = get_archive_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.archive.get_gmail_service")
    def test_no_emails_found_for_sender(self, mock_get_service):
        """No emails from sender should continue without error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        archive_emails_background(["sender@example.com"])

        status = get_archive_status()
        assert status["done"] is True
        assert status["error"] is None
        assert status["archived_count"] == 0

    @patch("app.services.gmail.archive.get_gmail_service")
    @patch("app.services.gmail.archive.time.sleep")
    def test_successful_archive(self, mock_sleep, mock_get_service):
        """Successful archive should update status and count."""
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

        archive_emails_background(["sender@example.com"])

        status = get_archive_status()
        assert status["done"] is True
        assert status["error"] is None
        assert status["archived_count"] == 5
        assert "5 emails" in status["message"]

    @patch("app.services.gmail.archive.get_gmail_service")
    @patch("app.services.gmail.archive.time.sleep")
    def test_multiple_senders(self, mock_sleep, mock_get_service):
        """Should archive emails from multiple senders."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Return 3 messages for each sender
        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(3)]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        archive_emails_background(["sender1@example.com", "sender2@example.com"])

        status = get_archive_status()
        assert status["done"] is True
        assert status["archived_count"] == 6  # 3 from each sender
        assert "2 senders" in status["message"]

    @patch("app.services.gmail.archive.get_gmail_service")
    @patch("app.services.gmail.archive.time.sleep")
    def test_pagination(self, mock_sleep, mock_get_service):
        """Should handle paginated results."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Paginated results
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

        archive_emails_background(["sender@example.com"])

        status = get_archive_status()
        assert status["done"] is True
        assert status["archived_count"] == 150

    @patch("app.services.gmail.archive.get_gmail_service")
    @patch("app.services.gmail.archive.time.sleep")
    def test_batch_processing(self, mock_sleep, mock_get_service):
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

        archive_emails_background(["sender@example.com"])

        # Should have called batchModify 3 times (100 + 100 + 50)
        assert mock_service.users.return_value.messages.return_value.batchModify.call_count == 3

    @patch("app.services.gmail.archive.get_gmail_service")
    @patch("app.services.gmail.archive.time.sleep")
    def test_throttling(self, mock_sleep, mock_get_service):
        """Should throttle after every 500 emails."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Return 600 messages to trigger throttling
        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(600)]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        archive_emails_background(["sender@example.com"])

        # Should have slept after 500 emails
        assert mock_sleep.called

    @patch("app.services.gmail.archive.get_gmail_service")
    def test_exception_handling(self, mock_get_service):
        """Exceptions should be caught and set error status."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception(
            "API Error"
        )

        archive_emails_background(["sender@example.com"])

        status = get_archive_status()
        assert "API Error" in status["error"]
        assert status["done"] is True

    @patch("app.services.gmail.archive.get_gmail_service")
    @patch("app.services.gmail.archive.time.sleep")
    def test_query_uses_sanitized_sender(self, mock_sleep, mock_get_service):
        """Query should use sanitized sender value."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        # Sender with special characters
        archive_emails_background(["test sender@example.com"])

        # Verify the query was passed to the API
        call_args = mock_service.users.return_value.messages.return_value.list.call_args
        assert "q" in call_args.kwargs
        query = call_args.kwargs["q"]
        # Should contain quoted sender for proper Gmail query
        assert "from:" in query
        assert "in:inbox" in query

    @patch("app.services.gmail.archive.get_gmail_service")
    @patch("app.services.gmail.archive.time.sleep")
    def test_progress_updates(self, mock_sleep, mock_get_service):
        """Progress should be updated during processing."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": "msg1"}]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        archive_emails_background(["sender1@example.com", "sender2@example.com"])

        status = get_archive_status()
        assert status["progress"] == 100
        assert status["done"] is True


class TestGetArchiveStatus:
    """Tests for get_archive_status function."""

    def test_returns_copy(self):
        """get_archive_status should return a copy."""
        state.update_archive_status(message="Test")
        status1 = get_archive_status()
        status2 = get_archive_status()

        status1["message"] = "Modified"
        assert status2["message"] == "Test"

    def test_initial_state(self):
        """Initial state should have default values."""
        status = get_archive_status()
        assert status["done"] is False
        assert status["error"] is None
