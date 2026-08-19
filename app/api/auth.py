"""
API Authentication
-------------------
Guards the API behind a shared secret whenever the server is reachable over
the network.

Threat model: after a user has OAuth'd their Gmail account, the action and
status endpoints can read and destroy mail using the stored credentials. They
must therefore not be callable by anyone who can merely reach the port.

Policy:
- A loopback-only bind (the default) is treated as trusted single-user use and
  needs no token.
- Any non-loopback bind requires a token. If ``API_TOKEN`` is not set, one is
  generated at startup so the API is never left open by accident.

The same-origin web UI authenticates automatically: the root page sets the
token as a cookie, which the browser then sends with every ``/api`` request.
"""

import logging
import secrets

from fastapi import HTTPException, Request, status

from app.core import settings

logger = logging.getLogger(__name__)

# Token enforced for this process. Resolved once at startup; ``None`` means the
# server is loopback-only and auth is disabled.
_effective_token: str | None = None
# True when the active token was generated rather than supplied via API_TOKEN.
_token_was_generated = False


def resolve_effective_token() -> str | None:
    """Decide whether API auth is required and which token enforces it.

    Returns the active token (or ``None`` when auth is disabled).
    """
    global _effective_token, _token_was_generated

    if settings.api_token:
        _effective_token = settings.api_token
        _token_was_generated = False
    elif not settings.is_loopback_host():
        # Reachable over the network but no token configured: refuse to run
        # open. Mint a random one so the operator gets a working, secured app.
        _effective_token = secrets.token_urlsafe(32)
        _token_was_generated = True
    else:
        _effective_token = None
        _token_was_generated = False

    return _effective_token


def get_effective_token() -> str | None:
    """Return the token currently enforced (``None`` if auth is disabled)."""
    return _effective_token


def token_was_generated() -> bool:
    """Return True if the active token was auto-generated at startup."""
    return _token_was_generated


def _extract_token(request: Request) -> str | None:
    """Pull a presented token from the Authorization header or a cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):].strip()

    explicit = request.headers.get("X-API-Token")
    if explicit:
        return explicit.strip()

    return request.cookies.get("api_token")


async def require_api_auth(request: Request) -> None:
    """FastAPI dependency enforcing the API token when one is in effect."""
    token = _effective_token
    if not token:
        # Loopback-only deployment: not network-reachable, no token required.
        return

    presented = _extract_token(request)
    if not presented or not secrets.compare_digest(presented, token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
