"""
Gmail Unread Email Operations
-----------------------------
Functions for scanning and managing unread emails by sender.
"""

import logging
import time
from collections import defaultdict
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

from app.core import state
from app.services.auth import get_gmail_service
from app.services.gmail.helpers import (
    build_gmail_query,
    get_sender_info,
    get_subject,
)


def _parse_email_date(date_str: str | None) -> datetime | None:
    """Parse email date string to datetime, handling various formats.

    Args:
        date_str: RFC 2822 formatted date string from email header

    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None

logger = logging.getLogger(__name__)


def scan_unread_by_sender(
    limit: int = 1000, filters: Optional[dict] = None, inbox_only: bool = True
):
    """Scan unread emails and group by sender.

    Args:
        limit: Maximum emails to scan
        filters: Optional filter dict (older_than, larger_than, category, sender, label)
        inbox_only: If True, use "is:unread in:inbox", otherwise "is:unread"
    """
    if limit <= 0:
        state.reset_unread_scan()
        state.update_unread_scan_status(error="Limit must be greater than 0", done=True)
        return

    state.reset_unread_scan()
    state.update_unread_scan_status(message="Connecting to Gmail...")

    service, error = get_gmail_service()
    if error:
        state.update_unread_scan_status(error=error, done=True)
        return

    try:
        state.update_unread_scan_status(message="Fetching unread emails...")

        # Build query: is:unread [in:inbox] + filters
        base_query = "is:unread in:inbox" if inbox_only else "is:unread"
        filter_query = build_gmail_query(filters)
        query = f"{base_query} {filter_query}".strip() if filter_query else base_query

        results = (
            service.users()
            .messages()
            .list(userId="me", maxResults=min(limit, 500), q=query)
            .execute()
        )

        messages = results.get("messages", [])

        while "nextPageToken" in results and len(messages) < limit:
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    maxResults=min(limit - len(messages), 500),
                    pageToken=results["nextPageToken"],
                    q=query,
                )
                .execute()
            )
            messages.extend(results.get("messages", []))

        messages = messages[:limit]
        total = len(messages)

        if total == 0:
            state.update_unread_scan_status(message="No unread emails found", done=True)
            return

        state.update_unread_scan_status(message=f"Scanning {total} unread emails...")

        # Group by sender using Gmail Batch API
        sender_counts: dict[str, dict] = defaultdict(
            lambda: {
                "count": 0,
                "sender": "",
                "email": "",
                "subjects": [],
                "first_date": None,
                "last_date": None,
                "message_ids": [],
                "total_size": 0,
            }
        )
        processed = 0
        batch_size = 100

        def process_message(request_id, response, exception) -> None:
            nonlocal processed
            processed += 1

            if exception:
                return

            headers = response.get("payload", {}).get("headers", [])
            sender_name, sender_email = get_sender_info(headers)
            subject = get_subject(headers)
            msg_id = response.get("id", "")
            size_estimate = response.get("sizeEstimate", 0)

            # Extract date from headers
            email_date_str = None
            for header in headers:
                if header["name"].lower() == "date":
                    email_date_str = header["value"]
                    break

            if sender_email:
                sender_counts[sender_email]["count"] += 1
                sender_counts[sender_email]["sender"] = sender_name
                sender_counts[sender_email]["email"] = sender_email
                sender_counts[sender_email]["message_ids"].append(msg_id)
                sender_counts[sender_email]["total_size"] += size_estimate
                if len(sender_counts[sender_email]["subjects"]) < 3:
                    sender_counts[sender_email]["subjects"].append(subject)

                # Track first (oldest) and last (newest) dates using proper comparison
                if email_date_str:
                    parsed_date = _parse_email_date(email_date_str)
                    if parsed_date:
                        sender_data = sender_counts[sender_email]
                        # Update first_date if this is older
                        existing_first = _parse_email_date(sender_data["first_date"])
                        if existing_first is None or parsed_date < existing_first:
                            sender_data["first_date"] = email_date_str
                        # Update last_date if this is newer
                        existing_last = _parse_email_date(sender_data["last_date"])
                        if existing_last is None or parsed_date > existing_last:
                            sender_data["last_date"] = email_date_str

        # Execute batch requests
        for i in range(0, len(messages), batch_size):
            batch_ids = messages[i : i + batch_size]
            batch = service.new_batch_http_request(callback=process_message)

            for msg_data in batch_ids:
                batch.add(
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg_data["id"],
                        format="metadata",
                        metadataHeaders=["From", "Subject", "Date"],
                    )
                )

            batch.execute()

            progress = int((i + len(batch_ids)) / total * 100)
            state.update_unread_scan_status(
                progress=progress, message=f"Scanned {processed}/{total} unread emails"
            )

            # Rate limiting
            if (i // batch_size + 1) % 5 == 0:
                time.sleep(0.3)

        # Sort by count
        sorted_senders = sorted(
            [{"email": k, **v} for k, v in sender_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        state.set_unread_scan_results(sorted_senders)
        state.update_unread_scan_status(
            message=f"Found {len(sorted_senders)} senders with unread emails", done=True
        )

    except Exception as e:
        logger.exception("Error scanning unread emails")
        state.update_unread_scan_status(error=str(e), done=True)


def get_unread_scan_status() -> dict:
    """Get unread scan status."""
    return state.get_unread_scan_status()


def get_unread_scan_results() -> list:
    """Get unread scan results."""
    return state.get_unread_scan_results()


def get_unread_action_status() -> dict:
    """Get unread action (mark read/archive) status."""
    return state.get_unread_action_status()


def mark_read_by_senders_background(senders: list[str]) -> None:
    """Mark all unread emails from specified senders as read.

    Uses batchModify with removeLabelIds: ["UNREAD"]
    """
    _process_unread_action(senders, action_name="mark as read", remove_labels=["UNREAD"])


def mark_read_and_archive_by_senders_background(senders: list[str]) -> None:
    """Mark as read and archive emails from specified senders.

    Uses batchModify with removeLabelIds: ["UNREAD", "INBOX"]
    """
    _process_unread_action(
        senders, action_name="mark as read and archive", remove_labels=["UNREAD", "INBOX"]
    )


def archive_unread_by_senders_background(senders: list[str]) -> None:
    """Archive unread emails (keep unread status, remove from inbox).

    Uses batchModify with removeLabelIds: ["INBOX"]
    """
    _process_unread_action(senders, action_name="archive", remove_labels=["INBOX"])


def delete_unread_by_senders_background(senders: list[str]) -> None:
    """Delete unread emails from specified senders (move to trash).

    Uses batchModify with addLabelIds: ["TRASH"]
    """
    _process_unread_action(senders, add_labels=["TRASH"], action_name="delete")


def _process_unread_action(
    senders: list[str],
    action_name: str,
    remove_labels: Optional[list[str]] = None,
    add_labels: Optional[list[str]] = None,
) -> None:
    """Process bulk unread action (mark read, archive, delete, or combinations).

    Args:
        senders: List of sender email addresses
        action_name: Human-readable action name for status messages
        remove_labels: Labels to remove (e.g., ["UNREAD"], ["INBOX"])
        add_labels: Labels to add (e.g., ["TRASH"] for delete)
    """
    state.reset_unread_action()

    if not senders or not isinstance(senders, list):
        state.update_unread_action_status(done=True, error="No senders specified")
        return

    total_senders = len(senders)
    state.update_unread_action_status(
        total_senders=total_senders, message=f"Collecting emails to {action_name}..."
    )

    service, error = get_gmail_service()
    if error:
        state.update_unread_action_status(done=True, error=error)
        return

    # Phase 1: Collect message IDs from cached scan results
    all_message_ids = []
    errors = []
    scan_results = state.get_unread_scan_results()

    for i, sender in enumerate(senders):
        progress = int((i / total_senders) * 40)  # 0-40% for collecting
        state.update_unread_action_status(
            current_sender=i + 1,
            progress=progress,
            message=f"Getting cached emails from {sender}...",
        )

        # Look up cached message_ids from scan results
        sender_data = next((r for r in scan_results if r.get("email") == sender), None)

        if sender_data and sender_data.get("message_ids"):
            all_message_ids.extend(sender_data["message_ids"])
        else:
            errors.append(f"{sender}: No scan results found")

    if not all_message_ids:
        state.update_unread_action_status(
            progress=100, done=True, message=f"No emails found to {action_name}"
        )
        return

    # Phase 2: Batch modify all collected IDs
    total_emails = len(all_message_ids)
    state.update_unread_action_status(
        message=f"Processing {total_emails} emails ({action_name})..."
    )

    batch_size = 1000  # Gmail allows up to 1000 per batchModify
    affected = 0

    try:
        for i in range(0, total_emails, batch_size):
            batch = all_message_ids[i : i + batch_size]
            body: dict = {"ids": batch}
            if remove_labels:
                body["removeLabelIds"] = remove_labels
            if add_labels:
                body["addLabelIds"] = add_labels
            service.users().messages().batchModify(userId="me", body=body).execute()
            affected += len(batch)
            # Progress: 40-100% for processing
            progress = 40 + int((affected / total_emails) * 60)
            state.update_unread_action_status(
                affected_count=affected,
                progress=progress,
                message=f"Processed {affected}/{total_emails} emails...",
            )
            # Rate limiting for large batches
            if i + batch_size < total_emails:
                time.sleep(0.2)
    except Exception as e:
        logger.exception(f"Error during {action_name}")
        errors.append(f"Batch modify error: {e!s}")

    # Atomically remove processed senders from cached scan results
    state.remove_senders_from_unread_results(set(senders))

    # Done
    if errors:
        state.update_unread_action_status(
            progress=100,
            done=True,
            affected_count=affected,
            error=f"Some errors: {'; '.join(errors[:3])}",
            message=f"Completed {action_name} for {affected} emails with some errors",
        )
    else:
        state.update_unread_action_status(
            progress=100,
            done=True,
            affected_count=affected,
            message=f"Successfully completed {action_name} for {affected} emails",
        )
