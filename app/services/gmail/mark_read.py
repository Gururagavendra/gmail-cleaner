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
        state.update_mark_read_status(error="Count must be 0 or greater", done=True)
        return

    state.reset_mark_read()
    state.update_mark_read_status(message="Connecting to Gmail...")

    service, error = get_gmail_service()
    if error:
        state.update_mark_read_status(error=error, done=True)
        return

    try:
        state.update_mark_read_status(message="Finding unread emails...")

        # Build query
        query = "is:unread"
        if filter_query := build_gmail_query(filters):
            query = f"{query} {filter_query}"

        # count=0 means "all" - no limit
        mark_all = count == 0
        page_size = 500
        batch_size = 100
        marked = 0
        remaining = count  # Only used when not mark_all
        page_token = None

        # Process messages in chunks as we paginate (memory efficient)
        while True:
            # Fetch a page of messages
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=page_size,
                    pageToken=page_token,
                )
                .execute()
            )

            messages = results.get("messages", [])
            if not messages:
                break

            # Slice to respect remaining count (unless marking all)
            if not mark_all:
                messages = messages[:remaining]
                remaining -= len(messages)

            # Mark this page in batches of 100
            for i in range(0, len(messages), batch_size):
                batch = messages[i : i + batch_size]
                ids = [msg["id"] for msg in batch]

                service.users().messages().batchModify(
                    userId="me", body={"ids": ids, "removeLabelIds": ["UNREAD"]}
                ).execute()

                marked += len(ids)
                state.update_mark_read_status(
                    message=f"Marked {marked} as read...", marked_count=marked
                )

            # Stop if we've marked enough (when not marking all)
            if not mark_all and remaining <= 0:
                break

            # Check for more pages
            page_token = results.get("nextPageToken")
            if not page_token:
                break

        if marked == 0:
            state.update_mark_read_status(
                message="No unread emails found", progress=100, done=True
            )
        else:
            state.update_mark_read_status(
                message=f"Done! Marked {marked} emails as read", progress=100, done=True
            )

    except Exception as e:
        state.update_mark_read_status(error=str(e), done=True)


def get_mark_read_status() -> dict:
    """Get mark-as-read status."""
    return state.mark_read_status.copy()
