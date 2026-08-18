"""
Tests for Gmail Scan Operations
--------------------------------
Tests for scan.py - scanning emails for unsubscribe links.
"""

from unittest.mock import Mock, patch

import pytest

from app.core import state
from app.services.gmail.scan import (
    scan_emails,
    get_scan_status,
    get_scan_results,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.reset_scan()
    yield
    state.reset_scan()


class TestScanEmails:
    """Tests for scan_emails function."""

    def test_invalid_limit_zero(self):
        """Zero limit should set error and return early."""
        scan_emails(limit=0)
        status = get_scan_status()
        assert status["error"] == "Limit must be greater than 0"
        assert status["done"] is True

    def test_invalid_limit_negative(self):
        """Negative limit should set error and return early."""
        scan_emails(limit=-10)
        status = get_scan_status()
        assert status["error"] == "Limit must be greater than 0"
        assert status["done"] is True

    @patch("app.services.gmail.scan.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        scan_emails(limit=100)

        status = get_scan_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.scan.get_gmail_service")
    def test_no_emails_found(self, mock_get_service):
        """Empty result should set appropriate message."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Mock the chained API calls to return empty list
        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        scan_emails(limit=100)

        status = get_scan_status()
        assert status["message"] == "No emails found"
        assert status["done"] is True
        assert status["error"] is None

    @patch("app.services.gmail.scan.get_gmail_service")
    @patch("app.services.gmail.scan.time.sleep")
    def test_successful_scan_with_unsubscribe(self, mock_sleep, mock_get_service):
        """Successful scan should find unsubscribe links."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Mock list to return message IDs
        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        # Mock batch request - callback is passed to new_batch_http_request
        batch_callback = None

        def mock_new_batch(callback):
            nonlocal batch_callback
            batch_callback = callback
            mock_batch = Mock()
            mock_batch.add = Mock()

            def mock_execute():
                # Simulate batch execution with callback responses
                responses = [
                    {
                        "id": "msg1",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Newsletter <news@domain1.com>"},
                                {"name": "Subject", "value": "Test Newsletter 1"},
                                {"name": "Date", "value": "Mon, 01 Jan 2024 10:00:00 +0000"},
                                {"name": "List-Unsubscribe", "value": "<https://domain1.com/unsub>"},
                            ]
                        },
                    },
                    {
                        "id": "msg2",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Alerts <alerts@domain2.com>"},
                                {"name": "Subject", "value": "Test Alert"},
                                {"name": "Date", "value": "Mon, 01 Jan 2024 11:00:00 +0000"},
                                {"name": "List-Unsubscribe", "value": "<https://domain2.com/unsub>"},
                            ]
                        },
                    },
                ]
                for i, resp in enumerate(responses):
                    batch_callback(f"req{i}", resp, None)

            mock_batch.execute = mock_execute
            return mock_batch

        mock_service.new_batch_http_request = mock_new_batch

        scan_emails(limit=10)

        status = get_scan_status()
        results = get_scan_results()

        assert status["done"] is True
        assert status["error"] is None
        assert len(results) == 2  # Two different domains
        assert results[0]["link"] is not None

    @patch("app.services.gmail.scan.get_gmail_service")
    @patch("app.services.gmail.scan.time.sleep")
    def test_scan_groups_by_domain(self, mock_sleep, mock_get_service):
        """Scan should group emails by domain."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Mock list to return message IDs
        mock_list = Mock()
        mock_list.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}, {"id": "msg3"}]
        }
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        # Mock batch request - callback is passed to new_batch_http_request
        def mock_new_batch(callback):
            mock_batch = Mock()
            mock_batch.add = Mock()

            def mock_execute():
                # Two messages from same domain, one from different
                responses = [
                    {
                        "id": "msg1",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "news@example.com"},
                                {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                            ]
                        },
                    },
                    {
                        "id": "msg2",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "updates@example.com"},
                                {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
                            ]
                        },
                    },
                    {
                        "id": "msg3",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "alerts@other.com"},
                                {"name": "List-Unsubscribe", "value": "<https://other.com/unsub>"},
                            ]
                        },
                    },
                ]
                for i, resp in enumerate(responses):
                    callback(f"req{i}", resp, None)

            mock_batch.execute = mock_execute
            return mock_batch

        mock_service.new_batch_http_request = mock_new_batch

        scan_emails(limit=10)

        results = get_scan_results()
        domains = [r["domain"] for r in results]

        assert "example.com" in domains
        assert "other.com" in domains

        # example.com should have count of 2
        example_result = next(r for r in results if r["domain"] == "example.com")
        assert example_result["count"] == 2

    @patch("app.services.gmail.scan.get_gmail_service")
    def test_exception_handling(self, mock_get_service):
        """Exceptions should be caught and set error status."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Mock list to raise exception
        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception(
            "API Error"
        )

        scan_emails(limit=100)

        status = get_scan_status()
        assert status["error"] == "API Error"
        assert status["done"] is True

    @patch("app.services.gmail.scan.get_gmail_service")
    def test_scan_with_filters(self, mock_get_service):
        """Scan should apply filters to query."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": []}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        filters = {"older_than": "30d", "category": "promotions"}
        scan_emails(limit=100, filters=filters)

        # Verify the query was passed to the API
        call_args = mock_service.users.return_value.messages.return_value.list.call_args
        assert "q" in call_args.kwargs

    @patch("app.services.gmail.scan.get_gmail_service")
    def test_pagination(self, mock_get_service):
        """Scan should handle pagination correctly."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Mock paginated results
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

        # Mock batch request that doesn't find unsubscribe links
        mock_batch = Mock()
        mock_batch.add = Mock()
        mock_batch.execute = Mock()
        mock_service.new_batch_http_request.return_value = mock_batch

        scan_emails(limit=200)

        # Should have made multiple list calls
        assert call_count[0] >= 2


class TestScanEmailsNoUnsubscribeLinks:
    """Tests for scan when emails don't have unsubscribe links."""

    @patch("app.services.gmail.scan.get_gmail_service")
    @patch("app.services.gmail.scan.time.sleep")
    def test_no_unsubscribe_links_found(self, mock_sleep, mock_get_service):
        """Scan should handle emails without unsubscribe links."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        mock_list = Mock()
        mock_list.execute.return_value = {"messages": [{"id": "msg1"}]}
        mock_service.users.return_value.messages.return_value.list.return_value = (
            mock_list
        )

        # Mock batch request with no unsubscribe header
        def mock_new_batch(callback):
            mock_batch = Mock()
            mock_batch.add = Mock()

            def mock_execute():
                response = {
                    "id": "msg1",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "friend@example.com"},
                            {"name": "Subject", "value": "Hello"},
                        ]
                    },
                }
                callback("req0", response, None)

            mock_batch.execute = mock_execute
            return mock_batch

        mock_service.new_batch_http_request = mock_new_batch

        scan_emails(limit=10)

        status = get_scan_status()
        results = get_scan_results()

        assert status["done"] is True
        assert len(results) == 0  # No unsubscribe links found


class TestStatusFunctions:
    """Tests for status retrieval functions."""

    def test_get_scan_status_returns_copy(self):
        """get_scan_status should return a copy."""
        state.update_scan_status(message="Test")
        status1 = get_scan_status()
        status2 = get_scan_status()

        status1["message"] = "Modified"
        assert status2["message"] == "Test"

    def test_get_scan_results_returns_copy(self):
        """get_scan_results should return a copy."""
        state.set_scan_results([{"domain": "test.com"}])
        results1 = get_scan_results()
        results2 = get_scan_results()

        results1.append({"domain": "new.com"})
        assert len(results2) == 1
