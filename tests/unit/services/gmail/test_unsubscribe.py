"""
Tests for Gmail Unsubscribe Operations
--------------------------------------
Tests for unsubscribe.py - unsubscribing from email senders.
"""

from unittest.mock import Mock, patch, MagicMock
import urllib.error

import pytest

from app.services.gmail.unsubscribe import unsubscribe_single


class TestUnsubscribeSingle:
    """Tests for unsubscribe_single function."""

    def test_no_link_provided(self):
        """Empty link should return failure."""
        result = unsubscribe_single("example.com", "")

        assert result["success"] is False
        assert result["message"] == "No unsubscribe link provided"

    def test_none_link_provided(self):
        """None link should return failure."""
        result = unsubscribe_single("example.com", None)

        assert result["success"] is False
        assert result["message"] == "No unsubscribe link provided"

    def test_mailto_link(self):
        """Mailto links should return special message."""
        result = unsubscribe_single("example.com", "mailto:unsubscribe@example.com")

        assert result["success"] is False
        assert result["type"] == "mailto"
        assert "email client" in result["message"].lower()

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    def test_ssrf_validation_failure(self, mock_validate):
        """SSRF validation failure should return security error."""
        mock_validate.side_effect = ValueError("Blocked restricted IP: 127.0.0.1")

        result = unsubscribe_single("example.com", "https://localhost/unsub")

        assert result["success"] is False
        assert "Security Error" in result["message"]
        assert "127.0.0.1" in result["message"]

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_successful_post_unsubscribe(self, mock_urlopen, mock_validate):
        """Successful POST request should return success."""
        mock_validate.return_value = "https://example.com/unsub"

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is True
        assert result["domain"] == "example.com"
        assert "successfully" in result["message"].lower()

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_successful_post_with_201_status(self, mock_urlopen, mock_validate):
        """POST returning 201 should succeed."""
        mock_validate.return_value = "https://example.com/unsub"

        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is True

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_successful_post_with_204_status(self, mock_urlopen, mock_validate):
        """POST returning 204 (No Content) should succeed."""
        mock_validate.return_value = "https://example.com/unsub"

        mock_response = MagicMock()
        mock_response.status = 204
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is True

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_post_fails_get_succeeds(self, mock_urlopen, mock_validate):
        """POST failure should fallback to GET."""
        mock_validate.return_value = "https://example.com/unsub"

        # POST fails, GET succeeds
        get_response = MagicMock()
        get_response.status = 200
        get_response.__enter__ = Mock(return_value=get_response)
        get_response.__exit__ = Mock(return_value=False)

        call_count = [0]

        def urlopen_side_effect(req, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (POST) fails
                raise urllib.error.URLError("Connection refused")
            else:
                # Second call (GET) succeeds
                return get_response

        mock_urlopen.side_effect = urlopen_side_effect

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is True
        assert "confirmation may be needed" in result["message"]

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_get_redirect_success(self, mock_urlopen, mock_validate):
        """GET returning 301/302 redirect should succeed."""
        mock_validate.return_value = "https://example.com/unsub"

        # POST fails
        get_response = MagicMock()
        get_response.status = 302
        get_response.__enter__ = Mock(return_value=get_response)
        get_response.__exit__ = Mock(return_value=False)

        call_count = [0]

        def urlopen_side_effect(req, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise urllib.error.URLError("POST failed")
            return get_response

        mock_urlopen.side_effect = urlopen_side_effect

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is True

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_both_methods_fail(self, mock_urlopen, mock_validate):
        """Both POST and GET failing should return failure."""
        mock_validate.return_value = "https://example.com/unsub"

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is False
        assert "Failed to unsubscribe" in result["message"]

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_http_error(self, mock_urlopen, mock_validate):
        """HTTP error should be handled gracefully."""
        mock_validate.return_value = "https://example.com/unsub"

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://example.com/unsub",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is False

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_timeout_error(self, mock_urlopen, mock_validate):
        """Timeout should be handled gracefully."""
        mock_validate.return_value = "https://example.com/unsub"

        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is False

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_get_returns_error_status(self, mock_urlopen, mock_validate):
        """GET returning error status should return failure."""
        mock_validate.return_value = "https://example.com/unsub"

        # POST fails
        get_response = MagicMock()
        get_response.status = 500
        get_response.__enter__ = Mock(return_value=get_response)
        get_response.__exit__ = Mock(return_value=False)

        call_count = [0]

        def urlopen_side_effect(req, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise urllib.error.URLError("POST failed")
            return get_response

        mock_urlopen.side_effect = urlopen_side_effect

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is False
        assert "status 500" in result["message"]

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_unexpected_exception(self, mock_urlopen, mock_validate):
        """Unexpected exception should be handled."""
        mock_validate.return_value = "https://example.com/unsub"

        mock_urlopen.side_effect = Exception("Unexpected error")

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is False

    @patch("app.services.gmail.unsubscribe.validate_unsafe_url")
    @patch("app.services.gmail.unsubscribe.urllib.request.urlopen")
    def test_long_error_message_truncated(self, mock_urlopen, mock_validate):
        """Long error messages should be truncated to 100 chars."""
        mock_validate.return_value = "https://example.com/unsub"

        long_message = "A" * 200
        mock_urlopen.side_effect = Exception(long_message)

        result = unsubscribe_single("example.com", "https://example.com/unsub")

        assert result["success"] is False
        assert len(result["message"]) <= 100
