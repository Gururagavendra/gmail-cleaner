"""
Gmail Archive Operations
------------------------
Functions for archiving emails (removing from inbox).
"""

import time

from app.core import state
from app.services.auth import get_gmail_service
from app.services.gmail.helpers import sanitize_gmail_query_value


def archive_emails_background(senders: list[str]):
    """Archive emails from selected senders (remove INBOX label)."""
    state.reset_archive()

    # Validate input
    if not senders or not isinstance(senders, list):
        state.update_archive_status(done=True, error="No senders specified")
        return

    state.update_archive_status(
        total_senders=len(senders), message="Starting archive..."
    )

    try:
        service, error = get_gmail_service()
        if error:
            state.update_archive_status(error=error, done=True)
            return

        total_archived = 0

        for i, sender in enumerate(senders):
            progress = int((i / len(senders)) * 100)
            state.update_archive_status(
                current_sender=i + 1,
                message=f"Archiving emails from {sender}...",
                progress=progress,
            )

            # Find all emails from this sender in INBOX
            query = f"from:{sanitize_gmail_query_value(sender)} in:inbox"
            message_ids = []
            page_token = None

            while True:
                result = (
                    service.users()
                    .messages()
                    .list(userId="me", q=query, maxResults=500, pageToken=page_token)
                    .execute()
                )

                messages = result.get("messages", [])
                message_ids.extend([m["id"] for m in messages])

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

            if not message_ids:
                continue

            # Archive in batches (remove INBOX label)
            for j in range(0, len(message_ids), 100):
                batch_ids = message_ids[j : j + 100]
                service.users().messages().batchModify(
                    userId="me", body={"ids": batch_ids, "removeLabelIds": ["INBOX"]}
                ).execute()
                total_archived += len(batch_ids)

                # Throttle every 500 emails (check at 100, 600, 1100, etc.)
                if (j + 100) % 500 == 0:
                    time.sleep(0.5)

        state.update_archive_status(
            progress=100,
            done=True,
            archived_count=total_archived,
            message=f"Archived {total_archived} emails from {len(senders)} senders",
        )

    except Exception as e:
        state.update_archive_status(
            error=f"{e!s}", done=True, message=f"Error: {e!s}"
        )


def get_archive_status() -> dict:
    """Get archive operation status."""
    return state.archive_status.copy()
