"""
Tests for Application Settings
------------------------------
Validation of environment-driven configuration.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


class TestOAuthRedirectUri:
    """Tests for the OAUTH_REDIRECT_URI setting."""

    def test_defaults_to_none(self):
        """Unset OAUTH_REDIRECT_URI leaves host/port composition in charge."""
        assert Settings(_env_file=None).oauth_redirect_uri is None

    @pytest.mark.parametrize(
        "value",
        [
            "https://gmail.example.com/",
            "https://gmail.example.com/oauth2/callback",
            "http://localhost:8767/",
        ],
    )
    def test_accepts_absolute_http_urls(self, value):
        """Any absolute http(s) URL is a legal redirect URI."""
        assert (
            Settings(_env_file=None, oauth_redirect_uri=value).oauth_redirect_uri
            == value
        )

    def test_strips_surrounding_whitespace(self):
        """Whitespace from an env file or compose block must not reach Google."""
        settings = Settings(
            _env_file=None, oauth_redirect_uri="  https://gmail.example.com/  "
        )
        assert settings.oauth_redirect_uri == "https://gmail.example.com/"

    @pytest.mark.parametrize("value", ["", "   "])
    def test_blank_is_treated_as_unset(self, value):
        """An empty override should fall back rather than produce an invalid URI."""
        assert (
            Settings(_env_file=None, oauth_redirect_uri=value).oauth_redirect_uri
            is None
        )

    @pytest.mark.parametrize(
        "value",
        [
            "gmail.example.com",  # no scheme
            "gmail.example.com:8767/",  # host:port parsed as scheme
            "ftp://gmail.example.com/",  # wrong scheme
            "https://",  # no host
        ],
    )
    def test_rejects_uris_google_would_refuse(self, value):
        """Fail at startup instead of surfacing redirect_uri_mismatch mid-flow."""
        with pytest.raises(ValidationError):
            Settings(_env_file=None, oauth_redirect_uri=value)
