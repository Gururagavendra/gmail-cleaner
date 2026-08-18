"""
Gmail Mark Important Operations
--------------------------------
Functions for marking/unmarking emails as important.
"""

import time

from app.core import state
from app.services.auth import get_gmail_service
from app.services.gmail.helpers import sanitize_gmail_query_value


def mark_important_background(senders: list[str], *, important: bool = True) -> None:
    """Mark/unmark emails from selected senders as important."""
    state.reset_important()

    # Validate input
    if not senders or not isinstance(senders, list):
        state.update_important_status(done=True, error="No senders specified")
        return

    action = "Marking" if important else "Unmarking"
    state.update_important_status(
        total_senders=len(senders), message=f"{action} as important..."
    )

    try:
        service, error = get_gmail_service()
        if error:
            state.update_important_status(error=error, done=True)
            return

        total_affected = 0

        for i, sender in enumerate(senders):
            progress = int((i / len(senders)) * 100)
            state.update_important_status(
                current_sender=i + 1,
                message=f"{action} emails from {sender}...",
                progress=progress,
            )

            # Find all emails from this sender
            query = f"from:{sanitize_gmail_query_value(sender)}"
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

            # Mark in batches
            for j in range(0, len(message_ids), 100):
                batch_ids = message_ids[j : j + 100]
                # Gmail API requires explicit parameter names (addLabelIds or removeLabelIds)
                body = (
                    {"ids": batch_ids, "addLabelIds": ["IMPORTANT"]}
                    if important
                    else {"ids": batch_ids, "removeLabelIds": ["IMPORTANT"]}
                )
                service.users().messages().batchModify(userId="me", body=body).execute()
                total_affected += len(batch_ids)

                # Throttle every 500 emails (use cumulative count across all senders)
                if total_affected > 0 and total_affected % 500 == 0:
                    time.sleep(0.5)

        action_done = "marked as important" if important else "unmarked as important"
        state.update_important_status(
            progress=100,
            done=True,
            affected_count=total_affected,
            message=f"{total_affected} emails {action_done}",
        )

    except Exception as e:
        state.update_important_status(
            error=f"{e!s}", done=True, message=f"Error: {e!s}"
        )


def get_important_status() -> dict:
    """Get mark important operation status."""
    return state.important_status.copy()
