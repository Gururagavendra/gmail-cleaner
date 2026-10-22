"""
Tests for Gmail Mark Important Operations
-----------------------------------------
Tests for important.py - marking/unmarking emails as important.
"""

from unittest.mock import Mock, patch

import pytest

from app.core import state
from app.services.gmail.important import (
    mark_important_background,
    get_important_status,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.reset_important()
    yield
    state.reset_important()


class TestMarkImportantBackground:
    """Tests for mark_important_background function."""

    def test_no_senders_empty_list(self):
        """Empty sender list should set error and return early."""
        mark_important_background([])

        status = get_important_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_no_senders_none(self):
        """None senders should set error and return early."""
        mark_important_background(None)

        status = get_important_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_invalid_senders_type(self):
        """Non-list senders should set error and return early."""
        mark_important_background("not-a-list")

        status = get_important_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.important.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        mark_important_background(["sender@example.com"])

        status = get_important_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.important.get_gmail_service")
    def test_no_emails_found_for_sender(self, mock_get_service):
        """No emails from sender should continue without error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mark_important_background(["sender@example.com"])

        status = get_important_status()
        assert status["done"] is True
        assert status["error"] is None
        assert status["affected_count"] == 0

    @patch("app.services.gmail.important.get_gmail_service")
    @patch("app.services.gmail.important.time.sleep")
    def test_successful_mark_important(self, mock_sleep, mock_get_service):
        """Successful marking should update status and count."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(5)]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        mark_important_background(["sender@example.com"], important=True)

        status = get_important_status()
        assert status["done"] is True
        assert status["error"] is None
        assert status["affected_count"] == 5
        assert "marked as important" in status["message"]

        # Verify addLabelIds was used
        call_args = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert "addLabelIds" in call_args.kwargs["body"]
        assert "IMPORTANT" in call_args.kwargs["body"]["addLabelIds"]

    @patch("app.services.gmail.important.get_gmail_service")
    @patch("app.services.gmail.important.time.sleep")
    def test_successful_unmark_important(self, mock_sleep, mock_get_service):
        """Successful unmarking should use removeLabelIds."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

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

        mark_important_background(["sender@example.com"], important=False)

        status = get_important_status()
        assert status["done"] is True
        assert "unmarked as important" in status["message"]

        # Verify removeLabelIds was used
        call_args = mock_service.users.return_value.messages.return_value.batchModify.call_args
        assert "removeLabelIds" in call_args.kwargs["body"]
        assert "IMPORTANT" in call_args.kwargs["body"]["removeLabelIds"]

    @patch("app.services.gmail.important.get_gmail_service")
    @patch("app.services.gmail.important.time.sleep")
    def test_multiple_senders(self, mock_sleep, mock_get_service):
        """Should process multiple senders."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

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

        mark_important_background(["sender1@example.com", "sender2@example.com"])

        status = get_important_status()
        assert status["done"] is True
        assert status["affected_count"] == 6  # 3 from each sender

    @patch("app.services.gmail.important.get_gmail_service")
    @patch("app.services.gmail.important.time.sleep")
    def test_pagination(self, mock_sleep, mock_get_service):
        """Should handle paginated results."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

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

        mark_important_background(["sender@example.com"])

        status = get_important_status()
        assert status["done"] is True
        assert status["affected_count"] == 150

    @patch("app.services.gmail.important.get_gmail_service")
    @patch("app.services.gmail.important.time.sleep")
    def test_batch_processing(self, mock_sleep, mock_get_service):
        """Should process in batches of 100."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

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

        mark_important_background(["sender@example.com"])

        # Should have called batchModify 3 times (100 + 100 + 50)
        assert mock_service.users.return_value.messages.return_value.batchModify.call_count == 3

    @patch("app.services.gmail.important.get_gmail_service")
    @patch("app.services.gmail.important.time.sleep")
    def test_throttling(self, mock_sleep, mock_get_service):
        """Should throttle every 500 emails."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": f"msg{i}"} for i in range(500)]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        mark_important_background(["sender@example.com"])

        # Should have slept after 500 emails
        assert mock_sleep.called

    @patch("app.services.gmail.important.get_gmail_service")
    def test_exception_handling(self, mock_get_service):
        """Exceptions should be caught and set error status."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception(
            "API Error"
        )

        mark_important_background(["sender@example.com"])

        status = get_important_status()
        assert "API Error" in status["error"]
        assert status["done"] is True

    @patch("app.services.gmail.important.get_gmail_service")
    @patch("app.services.gmail.important.time.sleep")
    def test_progress_updates(self, mock_sleep, mock_get_service):
        """Progress should be updated during processing."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": [{"id": "msg1"}]}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        mock_batch_modify = Mock()
        mock_batch_modify.execute.return_value = {}
        mock_service.users.return_value.messages.return_value.batchModify.return_value = (
            mock_batch_modify
        )

        mark_important_background(["sender1@example.com", "sender2@example.com"])

        status = get_important_status()
        assert status["progress"] == 100
        assert status["done"] is True


class TestGetImportantStatus:
    """Tests for get_important_status function."""

    def test_returns_copy(self):
        """get_important_status should return a copy."""
        state.update_important_status(message="Test")
        status1 = get_important_status()
        status2 = get_important_status()

        status1["message"] = "Modified"
        assert status2["message"] == "Test"

    def test_initial_state(self):
        """Initial state should have default values."""
        status = get_important_status()
        assert status["done"] is False
        assert status["error"] is None
