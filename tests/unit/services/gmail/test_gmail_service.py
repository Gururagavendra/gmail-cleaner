"""
Tests for Gmail Service Functions
---------------------------------
Tests for query building and email parsing helpers.
"""

from app.services.gmail import (
    build_gmail_query,
    _get_unsubscribe_from_headers,
    _get_sender_info,
    _get_subject,
)
from app.models.schemas import FiltersModel


class TestBuildGmailQuery:
    """Tests for build_gmail_query function."""

    def test_empty_filters(self):
        """Empty filters should return empty string."""
        assert build_gmail_query(None) == ""
        assert build_gmail_query({}) == ""

    def test_older_than_filter(self):
        """older_than filter should generate correct query."""
        filters = {"older_than": "30d"}
        assert build_gmail_query(filters) == "older_than:30d"

    def test_larger_than_filter(self):
        """larger_than filter should generate correct query."""
        filters = {"larger_than": "5M"}
        assert build_gmail_query(filters) == "larger:5M"

    def test_category_filter(self):
        """category filter should generate correct query."""
        filters = {"category": "promotions"}
        assert build_gmail_query(filters) == "category:promotions"

    def test_multiple_filters(self):
        """Multiple filters should be combined with spaces."""
        filters = {"older_than": "30d", "larger_than": "5M", "category": "promotions"}
        query = build_gmail_query(filters)
        assert "older_than:30d" in query
        assert "larger:5M" in query
        assert "category:promotions" in query

    def test_pydantic_model_input(self):
        """Should handle Pydantic FiltersModel."""
        filters = FiltersModel(older_than="30d", category="social")
        query = build_gmail_query(filters)
        assert "older_than:30d" in query
        assert "category:social" in query

    def test_empty_string_values_ignored(self):
        """Empty string values should be ignored."""
        filters = {"older_than": "", "larger_than": "5M", "category": ""}
        assert build_gmail_query(filters) == "larger:5M"

    def test_none_values_ignored(self):
        """None values should be ignored."""
        filters = {"older_than": None, "larger_than": "10M", "category": None}
        assert build_gmail_query(filters) == "larger:10M"


class TestGetUnsubscribeFromHeaders:
    """Tests for _get_unsubscribe_from_headers function."""

    def test_no_unsubscribe_header(self):
        """Should return None when no unsubscribe header."""
        headers = [
            {"name": "From", "value": "test@example.com"},
            {"name": "Subject", "value": "Test Email"},
        ]
        link, method = _get_unsubscribe_from_headers(headers)
        assert link is None
        assert method is None

    def test_standard_http_unsubscribe_link(self):
        """Should extract HTTP unsubscribe link."""
        headers = [
            {"name": "List-Unsubscribe", "value": "<https://example.com/unsubscribe>"},
        ]
        link, method = _get_unsubscribe_from_headers(headers)
        assert link == "https://example.com/unsubscribe"
        assert method == "manual"

    def test_one_click_unsubscribe(self):
        """Should detect one-click unsubscribe with POST header."""
        headers = [
            {"name": "List-Unsubscribe", "value": "<https://example.com/unsubscribe>"},
            {"name": "List-Unsubscribe-Post", "value": "List-Unsubscribe=One-Click"},
        ]
        link, method = _get_unsubscribe_from_headers(headers)
        assert link == "https://example.com/unsubscribe"
        assert method == "one-click"

    def test_mailto_fallback(self):
        """Should extract mailto link as fallback."""
        headers = [
            {"name": "List-Unsubscribe", "value": "<mailto:unsubscribe@example.com>"},
        ]
        link, method = _get_unsubscribe_from_headers(headers)
        assert link == "mailto:unsubscribe@example.com"
        assert method == "manual"

    def test_multiple_links_prefers_http(self):
        """Should prefer HTTP link over mailto."""
        headers = [
            {
                "name": "List-Unsubscribe",
                "value": "<mailto:unsub@example.com>, <https://example.com/unsub>",
            },
        ]
        link, method = _get_unsubscribe_from_headers(headers)
        # Code prefers HTTP links over mailto (checks https?:// first)
        assert link == "https://example.com/unsub"
        assert method == "manual"

    def test_case_insensitive_header_name(self):
        """Header name matching should be case-insensitive."""
        headers = [
            {"name": "LIST-UNSUBSCRIBE", "value": "<https://example.com/unsub>"},
        ]
        link, _method = _get_unsubscribe_from_headers(headers)
        assert link == "https://example.com/unsub"


class TestGetSenderInfo:
    """Tests for _get_sender_info function."""

    def test_standard_from_header(self):
        """Should parse standard From header with name and email."""
        headers = [
            {"name": "From", "value": "John Doe <john@example.com>"},
        ]
        name, email = _get_sender_info(headers)
        assert name == "John Doe"
        assert email == "john@example.com"

    def test_from_header_with_quoted_name(self):
        """Should handle quoted name in From header."""
        headers = [
            {"name": "From", "value": '"Company Newsletter" <news@company.com>'},
        ]
        name, email = _get_sender_info(headers)
        assert name == "Company Newsletter"
        assert email == "news@company.com"

    def test_from_header_email_only(self):
        """Should handle From header with just email."""
        headers = [
            {"name": "From", "value": "support@example.com"},
        ]
        name, email = _get_sender_info(headers)
        assert name == "support@example.com"
        assert email == "support@example.com"

    def test_from_header_with_angle_brackets_no_name(self):
        """Should handle email in angle brackets without name."""
        headers = [
            {"name": "From", "value": "<no-reply@example.com>"},
        ]
        _name, email = _get_sender_info(headers)
        assert email == "no-reply@example.com"

    def test_no_from_header(self):
        """Should return Unknown when no From header."""
        headers = [
            {"name": "Subject", "value": "Test"},
        ]
        name, email = _get_sender_info(headers)
        assert name == "Unknown"
        assert email == "unknown"

    def test_case_insensitive_header_name(self):
        """Header name matching should be case-insensitive."""
        headers = [
            {"name": "FROM", "value": "Test User <test@example.com>"},
        ]
        _name, email = _get_sender_info(headers)
        assert email == "test@example.com"


class TestGetSubject:
    """Tests for _get_subject function."""

    def test_standard_subject(self):
        """Should extract subject from headers."""
        headers = [
            {"name": "Subject", "value": "Welcome to our newsletter!"},
        ]
        assert _get_subject(headers) == "Welcome to our newsletter!"

    def test_no_subject_header(self):
        """Should return default when no Subject header."""
        headers = [
            {"name": "From", "value": "test@example.com"},
        ]
        assert _get_subject(headers) == "(No Subject)"

    def test_empty_subject(self):
        """Should return empty string for empty subject."""
        headers = [
            {"name": "Subject", "value": ""},
        ]
        assert _get_subject(headers) == ""

    def test_case_insensitive_header_name(self):
        """Header name matching should be case-insensitive."""
        headers = [
            {"name": "SUBJECT", "value": "Test Subject"},
        ]
        assert _get_subject(headers) == "Test Subject"

    def test_subject_with_special_characters(self):
        """Should handle subjects with special characters."""
        headers = [
            {"name": "Subject", "value": "🎉 Special Offer! 50% Off 🎁"},
        ]
        assert _get_subject(headers) == "🎉 Special Offer! 50% Off 🎁"


class TestSenderEmailForDeletion:
    """Tests for email extraction used in delete operations.

    The delete feature uses the email field from scan results to identify
    which sender's emails to delete. These tests verify email extraction
    produces valid addresses for the delete query.
    """

    def test_newsletter_sender_extracts_valid_email(self):
        """Newsletter sender should extract valid email for deletion."""
        headers = [
            {"name": "From", "value": "Newsletter <news@example.com>"},
            {"name": "List-Unsubscribe", "value": "<https://example.com/unsub>"},
        ]
        _name, email = _get_sender_info(headers)
        assert email == "news@example.com"
        assert "@" in email

    def test_promotional_sender_extracts_valid_email(self):
        """Promotional email sender should extract valid email."""
        headers = [
            {"name": "From", "value": '"Company Sales" <sales@company.com>'},
        ]
        _name, email = _get_sender_info(headers)
        assert email == "sales@company.com"
        assert "@" in email

    def test_extracted_email_usable_in_gmail_query(self):
        """Extracted email should be usable in from: query."""
        headers = [
            {"name": "From", "value": "Marketing Team <marketing@newsletter.example.com>"},
        ]
        _name, email = _get_sender_info(headers)
        query = f"from:{email}"
        assert query == "from:marketing@newsletter.example.com"
        assert " " not in email

    def test_sender_filter_query_construction(self):
        """Verify sender filter query is correctly constructed."""
        filters = {"sender": "newsletter@example.com"}
        query = build_gmail_query(filters)
        assert query == "from:newsletter@example.com"

    def test_email_with_subdomain_extracts_correctly(self):
        """Email with subdomain should extract correctly."""
        headers = [
            {"name": "From", "value": "Updates <updates@mail.service.example.com>"},
        ]
        _name, email = _get_sender_info(headers)
        assert email == "updates@mail.service.example.com"
        assert "@" in email

    def test_email_extraction_strips_whitespace(self):
        """Email extraction should handle headers with extra whitespace."""
        headers = [
            {"name": "From", "value": "  Newsletter  < news@example.com >"},
        ]
        _name, email = _get_sender_info(headers)
        assert email == "news@example.com"
        assert email.strip() == email
        assert "@" in email
