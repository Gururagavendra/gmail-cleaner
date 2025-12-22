"""
Gmail Mark as Read Operations
------------------------------
Functions for marking emails as read.
"""

from typing import Optional

from app.core import state
from app.services.auth import get_gmail_service
from app.services.gmail.helpers import build_gmail_query


def get_unread_count() -> dict:
    """Get estimated count of unread emails in Inbox (fast, for display)."""
    service, error = get_gmail_service()
    if error:
        return {"count": 0, "error": error}

    try:
        # Use resultSizeEstimate for fast display (1 API call)
        results = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread in:inbox", maxResults=1)
            .execute()
        )

        count = results.get("resultSizeEstimate", 0)
        return {"count": count}
    except Exception as e:
        return {"count": 0, "error": str(e)}


def mark_emails_as_read(count: int = 100, filters: Optional[dict] = None):
    """Mark unread emails as read.

    Args:
        count: Number of emails to mark. Use 0 to mark ALL unread emails.
        filters: Optional filters to apply.
    """
    # Validate input
    if count < 0:
        state.reset_mark_read()
        state.mark_read_status["error"] = "Count must be 0 or greater"
        state.mark_read_status["done"] = True
        return

    state.reset_mark_read()
    state.mark_read_status["message"] = "Connecting to Gmail..."

    service, error = get_gmail_service()
    if error:
        state.mark_read_status["error"] = error
        state.mark_read_status["done"] = True
        return

    try:
        state.mark_read_status["message"] = "Finding unread emails..."

        # Build query
        query = "is:unread"
        if filter_query := build_gmail_query(filters):
            query = f"{query} {filter_query}"

        # count=0 means "all" - no limit
        mark_all = count == 0
        limit = count if not mark_all else float("inf")

        # Fetch unread messages
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=500)
            .execute()
        )

        messages = results.get("messages", [])

        # Pagination - continue until we have enough or no more pages
        while "nextPageToken" in results and len(messages) < limit:
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=500,
                    pageToken=results["nextPageToken"],
                )
                .execute()
            )
            messages.extend(results.get("messages", []))

        # Trim to requested count (unless marking all)
        if not mark_all:
            messages = messages[:count]
        total = len(messages)

        if total == 0:
            state.mark_read_status["message"] = "No unread emails found"
            state.mark_read_status["done"] = True
            return

        # Batch mark as read
        batch_size = 100
        marked = 0

        for i in range(0, total, batch_size):
            batch = messages[i : i + batch_size]
            ids = [msg["id"] for msg in batch]

            service.users().messages().batchModify(
                userId="me", body={"ids": ids, "removeLabelIds": ["UNREAD"]}
            ).execute()

            marked += len(ids)
            progress = int(marked / total * 100)
            state.mark_read_status["progress"] = progress
            state.mark_read_status["message"] = f"Marked {marked}/{total} as read"
            state.mark_read_status["marked_count"] = marked

        state.mark_read_status["message"] = f"Done! Marked {marked} emails as read"
        state.mark_read_status["done"] = True

    except Exception as e:
        state.mark_read_status["error"] = str(e)
        state.mark_read_status["done"] = True


def get_mark_read_status() -> dict:
    """Get mark-as-read status."""
    return state.mark_read_status.copy()
