"""
Tests for Gmail Unread Email Operations
---------------------------------------
Tests for unread.py - scanning and managing unread emails by sender.
"""

from unittest.mock import Mock, patch

import pytest

from app.core import state
from app.services.gmail.unread import (
    scan_unread_by_sender,
    get_unread_scan_status,
    get_unread_scan_results,
    get_unread_action_status,
    mark_read_by_senders_background,
    mark_read_and_archive_by_senders_background,
    archive_unread_by_senders_background,
    delete_unread_by_senders_background,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.reset_unread_scan()
    state.reset_unread_action()
    yield
    state.reset_unread_scan()
    state.reset_unread_action()


class TestScanUnreadBySender:
    """Tests for scan_unread_by_sender function."""

    def test_invalid_limit_zero(self):
        """Zero limit should set error and return early."""
        scan_unread_by_sender(limit=0)

        status = get_unread_scan_status()
        assert status["error"] == "Limit must be greater than 0"
        assert status["done"] is True

    def test_invalid_limit_negative(self):
        """Negative limit should set error and return early."""
        scan_unread_by_sender(limit=-1)

        status = get_unread_scan_status()
        assert status["error"] == "Limit must be greater than 0"
        assert status["done"] is True

    @patch("app.services.gmail.unread.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        scan_unread_by_sender(limit=100)

        status = get_unread_scan_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.unread.get_gmail_service")
    def test_no_unread_emails(self, mock_get_service):
        """No unread emails should complete without error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        scan_unread_by_sender(limit=100)

        status = get_unread_scan_status()
        assert status["done"] is True
        assert status["error"] is None
        assert "No unread emails found" in status["message"]

    @patch("app.services.gmail.unread.get_gmail_service")
    def test_successful_scan_inbox_only(self, mock_get_service):
        """Successful scan with inbox_only=True should use correct query."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        scan_unread_by_sender(limit=100, inbox_only=True)

        # Check that the query includes "in:inbox"
        call_args = mock_service.users.return_value.messages.return_value.list.call_args
        assert "is:unread in:inbox" in call_args.kwargs.get("q", "")

    @patch("app.services.gmail.unread.get_gmail_service")
    def test_successful_scan_all_folders(self, mock_get_service):
        """Successful scan with inbox_only=False should not include 'in:inbox'."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        scan_unread_by_sender(limit=100, inbox_only=False)

        # Check that the query does not include "in:inbox"
        call_args = mock_service.users.return_value.messages.return_value.list.call_args
        query = call_args.kwargs.get("q", "")
        assert "is:unread" in query
        assert "in:inbox" not in query

    @patch("app.services.gmail.unread.get_gmail_service")
    @patch("app.services.gmail.unread.time.sleep")
    def test_successful_scan_groups_by_sender(self, mock_sleep, mock_get_service):
        """Successful scan should group emails by sender."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Return 3 messages from 2 senders
        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}, {"id": "msg3"}]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        # Mock batch requests
        def mock_new_batch(callback):
            batch = Mock()
            batch.add = Mock()

            def execute_batch():
                # Simulate batch responses for 3 messages from 2 senders
                messages = [
                    {
                        "id": "msg1",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "sender1@example.com"},
                                {"name": "Subject", "value": "Subject 1"},
                                {"name": "Date", "value": "Mon, 01 Jan 2025 10:00:00 +0000"},
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
                                {"name": "Date", "value": "Mon, 02 Jan 2025 10:00:00 +0000"},
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
                                {"name": "Date", "value": "Mon, 03 Jan 2025 10:00:00 +0000"},
                            ]
                        },
                        "sizeEstimate": 500,
                    },
                ]
                for i, msg in enumerate(messages):
                    callback(str(i), msg, None)

            batch.execute = execute_batch
            return batch

        mock_service.new_batch_http_request = mock_new_batch

        scan_unread_by_sender(limit=100)

        status = get_unread_scan_status()
        assert status["done"] is True
        assert status["error"] is None

        results = get_unread_scan_results()
        assert len(results) == 2  # 2 unique senders

        # Results should be sorted by count (descending)
        assert results[0]["count"] == 2  # sender1 has 2 emails
        assert results[1]["count"] == 1  # sender2 has 1 email


class TestMarkReadBySenders:
    """Tests for mark_read_by_senders_background function."""

    def test_no_senders_specified_empty_list(self):
        """Empty sender list should set error and return early."""
        mark_read_by_senders_background([])

        status = get_unread_action_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_no_senders_specified_none(self):
        """None senders should set error and return early."""
        mark_read_by_senders_background(None)

        status = get_unread_action_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.unread.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        mark_read_by_senders_background(["sender@example.com"])

        status = get_unread_action_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.unread.get_gmail_service")
    def test_no_cached_results(self, mock_get_service):
        """No cached scan results should complete with zero affected."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mark_read_by_senders_background(["sender@example.com"])

        status = get_unread_action_status()
        assert status["done"] is True
        assert "No emails found" in status["message"]


class TestMarkReadAndArchiveBySenders:
    """Tests for mark_read_and_archive_by_senders_background function."""

    def test_no_senders_specified(self):
        """Empty sender list should set error and return early."""
        mark_read_and_archive_by_senders_background([])

        status = get_unread_action_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.unread._process_unread_action")
    def test_calls_process_with_correct_labels(self, mock_process):
        """Should call _process_unread_action with remove_labels=['UNREAD', 'INBOX']."""
        senders = ["sender1@example.com", "sender2@example.com"]

        mark_read_and_archive_by_senders_background(senders)

        mock_process.assert_called_once_with(
            senders,
            action_name="mark as read and archive",
            remove_labels=["UNREAD", "INBOX"],
        )


class TestArchiveUnreadBySenders:
    """Tests for archive_unread_by_senders_background function."""

    def test_no_senders_specified(self):
        """Empty sender list should set error and return early."""
        archive_unread_by_senders_background([])

        status = get_unread_action_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.unread._process_unread_action")
    def test_calls_process_with_correct_labels(self, mock_process):
        """Should call _process_unread_action with remove_labels=['INBOX']."""
        senders = ["sender1@example.com", "sender2@example.com"]

        archive_unread_by_senders_background(senders)

        mock_process.assert_called_once_with(
            senders, action_name="archive", remove_labels=["INBOX"]
        )


class TestDeleteUnreadBySenders:
    """Tests for delete_unread_by_senders_background function."""

    def test_no_senders_specified(self):
        """Empty sender list should set error and return early."""
        delete_unread_by_senders_background([])

        status = get_unread_action_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_no_senders_specified_none(self):
        """None senders should set error and return early."""
        delete_unread_by_senders_background(None)

        status = get_unread_action_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.unread.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        delete_unread_by_senders_background(["sender@example.com"])

        status = get_unread_action_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.unread._process_unread_action")
    def test_calls_process_with_correct_labels(self, mock_process):
        """Should call _process_unread_action with add_labels=['TRASH']."""
        senders = ["sender1@example.com", "sender2@example.com"]

        delete_unread_by_senders_background(senders)

        mock_process.assert_called_once_with(
            senders, add_labels=["TRASH"], action_name="delete"
        )


class TestStatusFunctions:
    """Tests for status retrieval functions."""

    def test_get_unread_scan_status_returns_copy(self):
        """get_unread_scan_status should return a copy."""
        status1 = get_unread_scan_status()
        status2 = get_unread_scan_status()
        assert status1 is not status2

    def test_get_unread_scan_results_returns_copy(self):
        """get_unread_scan_results should return a copy."""
        results1 = get_unread_scan_results()
        results2 = get_unread_scan_results()
        assert results1 is not results2

    def test_get_unread_action_status_returns_copy(self):
        """get_unread_action_status should return a copy."""
        status1 = get_unread_action_status()
        status2 = get_unread_action_status()
        assert status1 is not status2

    def test_initial_scan_status(self):
        """Initial scan status should have expected fields."""
        status = get_unread_scan_status()
        assert "progress" in status
        assert "message" in status
        assert "done" in status
        assert "error" in status

    def test_initial_action_status(self):
        """Initial action status should have expected fields."""
        status = get_unread_action_status()
        assert "progress" in status
        assert "message" in status
        assert "done" in status
        assert "error" in status
        assert "affected_count" in status
        assert "total_senders" in status
        assert "current_sender" in status

    def test_remove_senders_from_unread_results_atomic(self):
        """remove_senders_from_unread_results should atomically filter results."""
        # Set up initial results
        initial_results = [
            {"email": "a@example.com", "count": 5},
            {"email": "b@example.com", "count": 3},
            {"email": "c@example.com", "count": 7},
        ]
        state.set_unread_scan_results(initial_results)

        # Remove some senders atomically
        state.remove_senders_from_unread_results({"a@example.com", "c@example.com"})

        # Verify only b@example.com remains
        results = state.get_unread_scan_results()
        assert len(results) == 1
        assert results[0]["email"] == "b@example.com"
        assert results[0]["count"] == 3

    def test_remove_senders_from_unread_results_empty_set(self):
        """remove_senders_from_unread_results with empty set should keep all."""
        initial_results = [
            {"email": "a@example.com", "count": 5},
            {"email": "b@example.com", "count": 3},
        ]
        state.set_unread_scan_results(initial_results)

        state.remove_senders_from_unread_results(set())

        results = state.get_unread_scan_results()
        assert len(results) == 2


class TestParseDateHelper:
    """Tests for _parse_email_date helper function."""

    def test_parse_valid_rfc2822_date(self):
        """Valid RFC 2822 date should be parsed correctly."""
        from app.services.gmail.unread import _parse_email_date

        result = _parse_email_date("Mon, 01 Jan 2024 10:00:00 +0000")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    def test_parse_none_returns_none(self):
        """None input should return None."""
        from app.services.gmail.unread import _parse_email_date

        assert _parse_email_date(None) is None

    def test_parse_empty_string_returns_none(self):
        """Empty string should return None."""
        from app.services.gmail.unread import _parse_email_date

        assert _parse_email_date("") is None

    def test_parse_invalid_date_returns_none(self):
        """Invalid date string should return None without raising."""
        from app.services.gmail.unread import _parse_email_date

        assert _parse_email_date("not a date") is None
        assert _parse_email_date("2024-01-01") is None  # ISO format not supported
