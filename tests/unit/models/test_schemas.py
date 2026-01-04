"""
Tests for Pydantic Models (schemas.py)
--------------------------------------
Validates request/response schemas and data validation.
"""

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    FiltersModel,
    ScanRequest,
    MarkReadRequest,
    DeleteBulkRequest,
    UnsubscribeRequest,
    DeleteEmailsRequest,
)


class TestFiltersModel:
    """Tests for FiltersModel validation."""

    def test_empty_filters_valid(self):
        """Empty filters should be valid."""
        filters = FiltersModel()
        assert filters.older_than is None
        assert filters.larger_than is None
        assert filters.category is None

    def test_valid_older_than_values(self):
        """Valid older_than formats should pass."""
        valid_values = ["7d", "30d", "90d", "180d", "365d", "1d", "999d"]
        for value in valid_values:
            filters = FiltersModel(older_than=value)
            assert filters.older_than == value

    def test_invalid_older_than_values(self):
        """Invalid older_than formats should fail."""
        invalid_values = ["7", "d", "7days", "1w", "1m", "1y", "abc", "7D"]
        for value in invalid_values:
            with pytest.raises(ValidationError):
                FiltersModel(older_than=value)

    def test_older_than_edge_cases(self):
        """Edge cases for older_than validation."""
        # Zero days - currently allowed by regex (matches \d+d)
        filters = FiltersModel(older_than="0d")
        assert filters.older_than == "0d"

        # Negative values - should be invalid (no minus in regex)
        with pytest.raises(ValidationError):
            FiltersModel(older_than="-7d")

        # Very large values - syntactically valid
        filters = FiltersModel(older_than="99999d")
        assert filters.older_than == "99999d"

    def test_valid_larger_than_values(self):
        """Valid larger_than formats should pass."""
        valid_values = ["1M", "5M", "10M", "1K", "100K", "1G", "1m", "5k"]
        for value in valid_values:
            filters = FiltersModel(larger_than=value)
            assert filters.larger_than == value

    def test_invalid_larger_than_values(self):
        """Invalid larger_than formats should fail."""
        invalid_values = ["1", "M", "1MB", "5mb", "10 M", "abc"]
        for value in invalid_values:
            with pytest.raises(ValidationError):
                FiltersModel(larger_than=value)

    def test_larger_than_edge_cases(self):
        """Edge cases for larger_than validation."""
        # Zero size - currently allowed by regex (matches \d+[KMG])
        filters = FiltersModel(larger_than="0M")
        assert filters.larger_than == "0M"

        # Negative values - should be invalid (no minus in regex)
        with pytest.raises(ValidationError):
            FiltersModel(larger_than="-5M")

        # Very large values - syntactically valid
        filters = FiltersModel(larger_than="99999M")
        assert filters.larger_than == "99999M"

    def test_valid_category_values(self):
        """Valid category values should pass and be normalized to lowercase."""
        valid_values = [
            "primary",
            "social",
            "promotions",
            "updates",
            "forums",
            "PRIMARY",
            "Social",
            "PROMOTIONS",
        ]
        for value in valid_values:
            filters = FiltersModel(category=value)
            assert filters.category == value.lower()

    def test_invalid_category_values(self):
        """Invalid category values should fail."""
        invalid_values = ["spam", "inbox", "trash", "important", "starred", "random"]
        for value in invalid_values:
            with pytest.raises(ValidationError):
                FiltersModel(category=value)

    def test_empty_string_treated_as_none(self):
        """Empty strings should be treated as None."""
        filters = FiltersModel(older_than="", larger_than="", category="")
        assert filters.older_than is None
        assert filters.larger_than is None
        assert filters.category is None

    def test_combined_filters(self):
        """Multiple filters should work together."""
        filters = FiltersModel(
            older_than="30d", larger_than="5M", category="promotions"
        )
        assert filters.older_than == "30d"
        assert filters.larger_than == "5M"
        assert filters.category == "promotions"


class TestScanRequest:
    """Tests for ScanRequest model."""

    def test_default_values(self):
        """Default values should be set correctly."""
        request = ScanRequest()
        assert request.limit == 500
        assert request.filters is None

    def test_valid_limit_range(self):
        """Limit within valid range should pass."""
        request = ScanRequest(limit=1000)
        assert request.limit == 1000

    def test_limit_minimum(self):
        """Minimum limit should be 1."""
        request = ScanRequest(limit=1)
        assert request.limit == 1

    def test_limit_maximum(self):
        """Maximum limit should be 5000."""
        request = ScanRequest(limit=5000)
        assert request.limit == 5000

    def test_limit_below_minimum(self):
        """Limit below 1 should fail."""
        with pytest.raises(ValidationError):
            ScanRequest(limit=0)

    def test_limit_above_maximum(self):
        """Limit above 5000 should fail."""
        with pytest.raises(ValidationError):
            ScanRequest(limit=5001)

    def test_with_filters(self):
        """Request with filters should work."""
        filters = FiltersModel(older_than="30d")
        request = ScanRequest(limit=100, filters=filters)
        assert request.limit == 100
        assert request.filters.older_than == "30d"


class TestMarkReadRequest:
    """Tests for MarkReadRequest model."""

    def test_default_values(self):
        """Default values should be set correctly."""
        request = MarkReadRequest()
        assert request.count == 100
        assert request.filters is None

    def test_count_maximum(self):
        """Maximum count should be 100000."""
        request = MarkReadRequest(count=100000)
        assert request.count == 100000

    def test_count_above_maximum(self):
        """Count above 100000 should fail."""
        with pytest.raises(ValidationError):
            MarkReadRequest(count=100001)


class TestDeleteBulkRequest:
    """Tests for DeleteBulkRequest model."""

    def test_empty_senders(self):
        """Empty senders list should be valid."""
        request = DeleteBulkRequest()
        assert request.senders == []

    def test_valid_senders_list(self):
        """Valid senders list should pass."""
        senders = ["user1@example.com", "user2@example.com"]
        request = DeleteBulkRequest(senders=senders)
        assert request.senders == senders

    def test_large_senders_list(self):
        """Should accept any number of senders (no limit)."""
        senders = [f"user{i}@example.com" for i in range(500)]
        request = DeleteBulkRequest(senders=senders)
        assert len(request.senders) == 500

    def test_very_large_senders_list(self):
        """Should accept very large sender lists."""
        senders = [f"user{i}@example.com" for i in range(1000)]
        request = DeleteBulkRequest(senders=senders)
        assert len(request.senders) == 1000


class TestUnsubscribeRequest:
    """Tests for UnsubscribeRequest model."""

    def test_default_values(self):
        """Default values should be empty strings."""
        request = UnsubscribeRequest()
        assert request.domain == ""
        assert request.link == ""

    def test_with_values(self):
        """Should accept domain and link."""
        request = UnsubscribeRequest(
            domain="example.com", link="https://example.com/unsub"
        )
        assert request.domain == "example.com"
        assert request.link == "https://example.com/unsub"


class TestDeleteEmailsRequest:
    """Tests for DeleteEmailsRequest model."""

    def test_default_values(self):
        """Default sender should be empty string."""
        request = DeleteEmailsRequest()
        assert request.sender == ""

    def test_with_sender(self):
        """Should accept sender email."""
        request = DeleteEmailsRequest(sender="newsletter@example.com")
        assert request.sender == "newsletter@example.com"
