"""
API Dependencies
----------------
Shared request context helpers for session-aware endpoints.
"""

import base64
import binascii
from dataclasses import dataclass

from fastapi import Header, Request

from app.core.state import SessionState, get_session_state


@dataclass(slots=True)
class SessionContext:
    """Per-request session context."""

    session_id: str
    session: SessionState
    token_json: str | None


def _decode_auth_token(encoded: str | None) -> str | None:
    """Decode base64 token JSON from header."""
    if not encoded:
        return None
    try:
        decoded = base64.b64decode(encoded.encode("utf-8"), validate=True)
    except (ValueError, binascii.Error):
        return None
    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError:
        return None


def get_session_context(
    request: Request,
    x_session_id: str | None = Header(default=None),
    x_auth_token: str | None = Header(default=None),
) -> SessionContext:
    """Build session context from headers/cookies."""
    session_id = x_session_id or request.cookies.get("gc_session") or "default"
    token_json = _decode_auth_token(x_auth_token)
    session = get_session_state(session_id)
    session.allow_token_file = not bool(x_session_id or request.cookies.get("gc_session"))
    if token_json:
        session.token_json = token_json
    return SessionContext(session_id=session_id, session=session, token_json=token_json)
