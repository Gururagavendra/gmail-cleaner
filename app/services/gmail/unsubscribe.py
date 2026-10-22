"""
Gmail Unsubscribe Operations
----------------------------
Functions for unsubscribing from email senders.
"""

import logging
import urllib.error
import urllib.request

from app.services.gmail.helpers import validate_unsafe_url

logger = logging.getLogger(__name__)


def unsubscribe_single(domain: str, link: str) -> dict:
    """Attempt to unsubscribe from a single sender."""
    if not link:
        return {"success": False, "message": "No unsubscribe link provided"}

    # Handle mailto: links
    if link.startswith("mailto:"):
        return {
            "success": False,
            "message": "Email-based unsubscribe - open in email client",
            "type": "mailto",
        }

    try:
        # Validate URL for SSRF (Check scheme and block private/loopback IPs)
        try:
            link = validate_unsafe_url(link)
        except ValueError as e:
            return {"success": False, "message": f"Security Error: {e!s}"}

        # Create Default SSL context (Verifies certs by default)
        # We removed the custom context that disabled verification.

        # Try POST first (one-click), then GET
        req = urllib.request.Request(
            link,
            data=b"List-Unsubscribe=One-Click",
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; GmailUnsubscribe/1.0)",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310
                if response.status in [200, 201, 202, 204]:
                    return {
                        "success": True,
                        "message": "Unsubscribed successfully",
                        "domain": domain,
                    }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            # POST failed - log and fall back to GET
            logger.debug(
                f"POST unsubscribe failed for {domain}, falling back to GET: {e}"
            )
        except Exception as e:
            # Unexpected error - log it
            logger.warning(
                f"Unexpected error during POST unsubscribe for {domain}: {e}"
            )

        # Fallback to GET
        req = urllib.request.Request(
            link,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GmailUnsubscribe/1.0)"},
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310
                if response.status in [200, 201, 202, 204, 301, 302]:
                    return {
                        "success": True,
                        "message": "Unsubscribed (confirmation may be needed)",
                        "domain": domain,
                    }
                return {
                    "success": False,
                    "message": f"Server returned status {response.status}",
                }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            return {"success": False, "message": f"Failed to unsubscribe: {e}"}

    except Exception as e:
        return {"success": False, "message": str(e)[:100]}
