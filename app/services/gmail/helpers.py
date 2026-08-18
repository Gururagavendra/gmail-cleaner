"""
Gmail Service Helpers
---------------------
Shared utility functions: security, filters, and email parsing.
"""

import re
import socket
import ipaddress
from urllib.parse import urlparse
from typing import Optional, Union, Any


def sanitize_gmail_query_value(value: str) -> str:
    """Sanitize a value for safe use in Gmail search queries.

    Gmail query syntax uses special operators (OR, AND, -, (), etc.) that could
    be injected via unsanitized user input. This function quotes the value to
    ensure it's treated as a literal string.

    Args:
        value: The raw value to sanitize (e.g., email address, domain)

    Returns:
        A quoted string safe for use in Gmail queries

    Examples:
        >>> sanitize_gmail_query_value("user@example.com")
        '"user@example.com"'
        >>> sanitize_gmail_query_value('evil@test.com OR from:admin@company.com')
        '"evil@test.com OR from:admin@company.com"'
        >>> sanitize_gmail_query_value('user"with"quotes@test.com')
        '"user\\"with\\"quotes@test.com"'
    """
    if not value:
        return ""

    # Escape any existing backslashes first, then escape quotes
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')

    # Wrap in quotes to treat as literal
    return f'"{escaped}"'


def validate_unsafe_url(url: str) -> str:
    """
    Validate URL to prevent SSRF.
    Checks scheme and resolves hostname to ensure it's not a local/private IP.

    Resolves all A and AAAA records to prevent DNS rebinding attacks where
    a hostname resolves to a safe IP during validation but a malicious IP
    during actual request. All resolved IPs must pass validation.

    TOCTOU Risk Warning:
    This validation occurs before the request, but DNS could still change
    between validation and request time. For complete protection against
    DNS rebinding attacks, callers should:
    1. Use the validated IPs directly (if possible) instead of the hostname
    2. Implement request-level IP validation in the HTTP client
    3. Use a custom HTTP client that validates IPs at request time

    Returns:
        The validated URL string (unchanged).
    """
    try:
        parsed = urlparse(url)
    except Exception as err:
        raise ValueError("Invalid URL format") from err

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Invalid URL scheme. Only HTTP and HTTPS are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: No hostname found.")

    # Resolve all A and AAAA records to prevent DNS rebinding
    # Validate all IPs - all must be safe
    # Note: This pins the IPs at validation time, but DNS could still change
    # between validation and actual request (TOCTOU risk).
    validated_ips = []
    try:
        # Get all address info (both IPv4 and IPv6)
        addr_infos = socket.getaddrinfo(
            hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )

        for addr_info in addr_infos:
            # addr_info[4] is (host, port) tuple
            ip_str = addr_info[4][0]

            try:
                ip = ipaddress.ip_address(ip_str)

                # Check for restricted IP ranges
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_unspecified
                ):
                    raise ValueError(f"Blocked restricted IP: {ip_str}")

                validated_ips.append(ip_str)
            except ValueError as err:
                # If any IP is invalid or restricted, reject the URL
                raise ValueError(f"Invalid or restricted IP address: {ip_str}") from err

        if not validated_ips:
            raise ValueError(
                f"Could not resolve any valid IP addresses for hostname: {hostname}"
            )

    except socket.gaierror as err:
        raise ValueError(f"Could not resolve hostname: {hostname}") from err
    except ValueError:
        # Re-raise our own ValueError with context (already chained above)
        raise

    return url


def build_gmail_query(filters: Optional[Union[dict, Any]] = None) -> str:
    """Build Gmail search query from filter parameters.

    Args:
        filters: dict with keys:
            - older_than: '7d', '30d', '90d', '180d', '365d' or empty (for relative dates)
            - after_date: 'YYYY/MM/DD' for emails after this date
            - before_date: 'YYYY/MM/DD' for emails before this date
            - larger_than: '1M', '5M', '10M', '25M' or empty
            - category: 'promotions', 'social', 'updates', 'forums', 'primary' or empty
            - sender: 'email@domain.com' or 'domain.com' to filter by sender

    Returns:
        Gmail query string, empty string if no filters
    """
    if not filters:
        return ""

    # Handle both dict and Pydantic model
    if hasattr(filters, "model_dump"):
        filters = filters.model_dump(exclude_none=True)

    query_parts = []

    # Use after/before dates if provided (custom date range)
    if after_date := filters.get("after_date", ""):
        query_parts.append(f"after:{after_date}")

    if before_date := filters.get("before_date", ""):
        query_parts.append(f"before:{before_date}")

    # Fall back to older_than for preset options
    if not after_date and not before_date:
        if older_than := filters.get("older_than", ""):
            query_parts.append(f"older_than:{older_than}")

    if larger_than := filters.get("larger_than", ""):
        query_parts.append(f"larger:{larger_than}")

    if category := filters.get("category", ""):
        query_parts.append(f"category:{category}")

    if sender := filters.get("sender", ""):
        query_parts.append(f"from:{sanitize_gmail_query_value(sender)}")

    if label := filters.get("label", ""):
        query_parts.append(f"label:{sanitize_gmail_query_value(label)}")

    return " ".join(query_parts)


def get_unsubscribe_from_headers(headers: list) -> tuple[Optional[str], Optional[str]]:
    """Extract unsubscribe link from email headers."""
    for header in headers:
        if header["name"].lower() == "list-unsubscribe":
            value = header["value"]

            # Look for one-click POST header
            for h in headers:
                if h["name"].lower() == "list-unsubscribe-post":
                    # Has one-click support
                    urls = re.findall(r"<(https?://[^>]+)>", value)
                    if urls:
                        return urls[0], "one-click"

            # Standard unsubscribe link
            urls = re.findall(r"<(https?://[^>]+)>", value)
            if urls:
                return urls[0], "manual"

            # mailto: link as fallback
            mailto = re.findall(r"<(mailto:[^>]+)>", value)
            if mailto:
                return mailto[0], "manual"

    return None, None


def get_sender_info(headers: list) -> tuple[str, str]:
    """Extract sender name and email from headers."""
    for header in headers:
        if header["name"].lower() == "from":
            from_value = header["value"]
            match = re.search(r"([^<]*)<([^>]+)>", from_value)
            if match:
                name = match.group(1).strip().strip('"')
                email = match.group(2).strip()
                return name or email, email
            return from_value, from_value
    return "Unknown", "unknown"


def get_subject(headers: list) -> str:
    """Extract subject from email headers."""
    for header in headers:
        if header["name"].lower() == "subject":
            return header["value"]
    return "(No Subject)"
