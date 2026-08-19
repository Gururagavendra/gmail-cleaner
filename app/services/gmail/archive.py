"""
Gmail Archive Operations
------------------------
Functions for archiving emails (removing from inbox).
"""

import time

from app.core.state import SessionState
from app.services.auth import get_gmail_service


def archive_emails_background(session: SessionState, senders: list[str]):
    """Archive emails from selected senders (remove INBOX label)."""
    session.reset_archive()

    # Validate input
    if not senders or not isinstance(senders, list):
        session.archive_status["done"] = True
        session.archive_status["error"] = "No senders specified"
        return

    session.archive_status["total_senders"] = len(senders)
    session.archive_status["message"] = "Starting archive..."

    try:
        service, error = get_gmail_service(session)
        if error:
            session.archive_status["error"] = error
            session.archive_status["done"] = True
            return

        total_archived = 0

        for i, sender in enumerate(senders):
            session.archive_status["current_sender"] = i + 1
            session.archive_status["message"] = f"Archiving emails from {sender}..."
            session.archive_status["progress"] = int((i / len(senders)) * 100)

            # Find all emails from this sender in INBOX
            query = f"from:{sender} in:inbox"
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

        session.archive_status["progress"] = 100
        session.archive_status["done"] = True
        session.archive_status["archived_count"] = total_archived
        session.archive_status["message"] = (
            f"Archived {total_archived} emails from {len(senders)} senders"
        )

    except Exception as e:
        session.archive_status["error"] = f"{e!s}"
        session.archive_status["done"] = True
        session.archive_status["message"] = f"Error: {e!s}"


def get_archive_status(session: SessionState) -> dict:
    """Get archive operation status."""
    return session.archive_status.copy()
