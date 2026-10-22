"""
Tests for Gmail Download Operations
-----------------------------------
Tests for download.py - downloading email metadata as CSV.
"""

from unittest.mock import Mock, patch

import pytest

from app.core import state
from app.services.gmail.download import (
    download_emails_background,
    get_download_status,
    get_download_csv,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.reset_download()
    state.reset_delete_scan()
    yield
    state.reset_download()
    state.reset_delete_scan()


class TestDownloadEmailsBackground:
    """Tests for download_emails_background function."""

    def test_no_senders_empty_list(self):
        """Empty sender list should set error and return early."""
        download_emails_background([])

        status = get_download_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_no_senders_none(self):
        """None senders should set error and return early."""
        download_emails_background(None)

        status = get_download_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    def test_invalid_senders_type(self):
        """Non-list senders should set error and return early."""
        download_emails_background("not-a-list")

        status = get_download_status()
        assert status["error"] == "No senders specified"
        assert status["done"] is True

    @patch("app.services.gmail.download.get_gmail_service")
    def test_auth_error(self, mock_get_service):
        """Auth error should set error status."""
        mock_get_service.return_value = (None, "Authentication required")

        download_emails_background(["sender@example.com"])

        status = get_download_status()
        assert status["error"] == "Authentication required"
        assert status["done"] is True

    @patch("app.services.gmail.download.get_gmail_service")
    def test_no_emails_in_scan_results(self, mock_get_service):
        """No matching emails in scan results should set error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Empty scan results
        state.set_delete_scan_results([])

        download_emails_background(["sender@example.com"])

        status = get_download_status()
        assert status["error"] == "No emails found in scan results"
        assert status["done"] is True

    @patch("app.services.gmail.download.get_gmail_service")
    def test_sender_not_in_scan_results(self, mock_get_service):
        """Sender not matching scan results should set error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Scan results with different sender
        state.set_delete_scan_results([
            {"email": "other@example.com", "message_ids": ["msg1", "msg2"]}
        ])

        download_emails_background(["sender@example.com"])

        status = get_download_status()
        assert status["error"] == "No emails found in scan results"
        assert status["done"] is True

    @patch("app.services.gmail.download.get_gmail_service")
    @patch("app.services.gmail.download.time.sleep")
    def test_successful_download(self, mock_sleep, mock_get_service):
        """Successful download should generate CSV."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Set up scan results
        state.set_delete_scan_results([
            {"email": "sender@example.com", "message_ids": ["msg1", "msg2"]}
        ])

        # Mock batch request - must handle callback kwarg pattern
        callbacks = []

        def mock_add(request, callback):
            callbacks.append(callback)

        def mock_execute():
            responses = [
                {
                    "id": "msg1",
                    "threadId": "thread1",
                    "snippet": "Test snippet 1",
                    "labelIds": ["INBOX"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Sender <sender@example.com>"},
                            {"name": "Subject", "value": "Test Subject 1"},
                            {"name": "Date", "value": "Mon, 01 Jan 2024 10:00:00 +0000"},
                        ],
                        "body": {"data": ""},
                    },
                },
                {
                    "id": "msg2",
                    "threadId": "thread2",
                    "snippet": "Test snippet 2",
                    "labelIds": ["INBOX", "UNREAD"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "sender@example.com"},
                            {"name": "Subject", "value": "Test Subject 2"},
                            {"name": "Date", "value": "Tue, 02 Jan 2024 10:00:00 +0000"},
                        ],
                        "body": {"data": ""},
                    },
                },
            ]
            for i, cb in enumerate(callbacks):
                if i < len(responses):
                    cb(f"req{i}", responses[i], None)
            callbacks.clear()

        mock_batch = Mock()
        mock_batch.add = mock_add
        mock_batch.execute = mock_execute
        mock_service.new_batch_http_request.return_value = mock_batch

        download_emails_background(["sender@example.com"])

        status = get_download_status()
        assert status["done"] is True
        assert status["error"] is None
        assert "2 emails" in status["message"]

        csv_data = get_download_csv()
        assert csv_data is not None
        assert "message_id" in csv_data
        assert "msg1" in csv_data
        assert "msg2" in csv_data
        assert "Test Subject 1" in csv_data

    @patch("app.services.gmail.download.get_gmail_service")
    @patch("app.services.gmail.download.time.sleep")
    def test_multiple_senders(self, mock_sleep, mock_get_service):
        """Should download from multiple senders."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        state.set_delete_scan_results([
            {"email": "sender1@example.com", "message_ids": ["msg1"]},
            {"email": "sender2@example.com", "message_ids": ["msg2"]},
        ])

        def mock_new_batch():
            mock_batch = Mock()
            mock_batch._callbacks = []

            def add_request(request, callback):
                mock_batch._callbacks.append(callback)

            def execute():
                for i, callback in enumerate(mock_batch._callbacks):
                    callback(f"req{i}", {
                        "id": f"msg{i+1}",
                        "threadId": f"thread{i+1}",
                        "snippet": f"Snippet {i+1}",
                        "labelIds": [],
                        "payload": {"headers": [], "body": {"data": ""}},
                    }, None)

            mock_batch.add = add_request
            mock_batch.execute = execute
            return mock_batch

        mock_service.new_batch_http_request = mock_new_batch

        download_emails_background(["sender1@example.com", "sender2@example.com"])

        status = get_download_status()
        assert status["done"] is True
        assert status["error"] is None

    @patch("app.services.gmail.download.get_gmail_service")
    def test_fetch_exception(self, mock_get_service):
        """Exception during fetch should set error."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        state.set_delete_scan_results([
            {"email": "sender@example.com", "message_ids": ["msg1"]}
        ])

        mock_service.new_batch_http_request.side_effect = Exception("API Error")

        download_emails_background(["sender@example.com"])

        status = get_download_status()
        assert status["done"] is True
        assert "Error fetching emails" in status["error"]

    @patch("app.services.gmail.download.get_gmail_service")
    @patch("app.services.gmail.download.time.sleep")
    def test_rate_limiting(self, mock_sleep, mock_get_service):
        """Should sleep for rate limiting on large batches."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        # Create many message IDs to trigger rate limiting
        state.set_delete_scan_results([
            {"email": "sender@example.com", "message_ids": [f"msg{i}" for i in range(300)]}
        ])

        def mock_new_batch():
            mock_batch = Mock()
            mock_batch._callbacks = []

            def add_request(request, callback):
                mock_batch._callbacks.append(callback)

            def execute():
                for i, callback in enumerate(mock_batch._callbacks):
                    callback(f"req{i}", {
                        "id": f"msg{i}",
                        "threadId": f"thread{i}",
                        "snippet": "",
                        "labelIds": [],
                        "payload": {"headers": [], "body": {"data": ""}},
                    }, None)

            mock_batch.add = add_request
            mock_batch.execute = execute
            return mock_batch

        mock_service.new_batch_http_request = mock_new_batch

        download_emails_background(["sender@example.com"])

        # Should have called sleep for rate limiting
        assert mock_sleep.called

    @patch("app.services.gmail.download.get_gmail_service")
    @patch("app.services.gmail.download.time.sleep")
    def test_email_body_extraction_plain_text(self, mock_sleep, mock_get_service):
        """Should extract plain text body from email."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        import base64
        body_content = base64.urlsafe_b64encode(b"Hello, this is the email body").decode()

        state.set_delete_scan_results([
            {"email": "sender@example.com", "message_ids": ["msg1"]}
        ])

        def mock_new_batch():
            mock_batch = Mock()
            mock_batch._callbacks = []

            def add_request(request, callback):
                mock_batch._callbacks.append(callback)

            def execute():
                callback = mock_batch._callbacks[0]
                callback("req0", {
                    "id": "msg1",
                    "threadId": "thread1",
                    "snippet": "",
                    "labelIds": [],
                    "payload": {
                        "headers": [],
                        "body": {"data": body_content},
                    },
                }, None)

            mock_batch.add = add_request
            mock_batch.execute = execute
            return mock_batch

        mock_service.new_batch_http_request = mock_new_batch

        download_emails_background(["sender@example.com"])

        csv_data = get_download_csv()
        assert "Hello, this is the email body" in csv_data

    @patch("app.services.gmail.download.get_gmail_service")
    @patch("app.services.gmail.download.time.sleep")
    def test_email_body_multipart(self, mock_sleep, mock_get_service):
        """Should extract body from multipart email."""
        mock_service = Mock()
        mock_get_service.return_value = (mock_service, None)

        import base64
        plain_body = base64.urlsafe_b64encode(b"Plain text body").decode()

        state.set_delete_scan_results([
            {"email": "sender@example.com", "message_ids": ["msg1"]}
        ])

        def mock_new_batch():
            mock_batch = Mock()
            mock_batch._callbacks = []

            def add_request(request, callback):
                mock_batch._callbacks.append(callback)

            def execute():
                callback = mock_batch._callbacks[0]
                callback("req0", {
                    "id": "msg1",
                    "threadId": "thread1",
                    "snippet": "",
                    "labelIds": [],
                    "payload": {
                        "headers": [],
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": plain_body},
                            },
                            {
                                "mimeType": "text/html",
                                "body": {"data": base64.urlsafe_b64encode(b"<html>HTML body</html>").decode()},
                            },
                        ],
                    },
                }, None)

            mock_batch.add = add_request
            mock_batch.execute = execute
            return mock_batch

        mock_service.new_batch_http_request = mock_new_batch

        download_emails_background(["sender@example.com"])

        csv_data = get_download_csv()
        # Should prefer plain text over HTML
        assert "Plain text body" in csv_data


class TestGetDownloadStatus:
    """Tests for get_download_status function."""

    def test_returns_status_without_csv(self):
        """get_download_status should not include CSV data."""
        state.update_download_status(csv_data="some,csv,data", message="Test")

        status = get_download_status()
        assert "csv_data" not in status
        assert status["message"] == "Test"

    def test_initial_state(self):
        """Initial state should have default values."""
        status = get_download_status()
        assert status["done"] is False
        assert status["error"] is None
        assert status["progress"] == 0


class TestGetDownloadCsv:
    """Tests for get_download_csv function."""

    def test_returns_csv_data(self):
        """get_download_csv should return CSV data when available."""
        state.update_download_status(csv_data="message_id,from\nmsg1,test@example.com")

        csv = get_download_csv()
        assert csv == "message_id,from\nmsg1,test@example.com"

    def test_returns_none_when_no_data(self):
        """get_download_csv should return None when no CSV available."""
        csv = get_download_csv()
        assert csv is None
