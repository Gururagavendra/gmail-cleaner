"""
Gmail Delete Operations
-----------------------
Functions for deleting emails and scanning senders.
"""

import logging
import re
import time
from collections import defaultdict
from typing import Optional

from app.core.state import SessionState
from app.services.auth import get_gmail_service
from app.services.gmail.helpers import build_gmail_query, get_sender_info, get_subject

logger = logging.getLogger(__name__)


def scan_senders_for_delete(
    session: SessionState, limit: int = 1000, filters: Optional[dict] = None
):
    """Scan emails and group by sender for bulk delete."""
    # Validate input
    if limit <= 0:
        session.reset_delete_scan()
        session.delete_scan_status["error"] = "Limit must be greater than 0"
        session.delete_scan_status["done"] = True
        return

    session.reset_delete_scan()
    session.delete_scan_status["message"] = "Connecting to Gmail..."

    service, error = get_gmail_service(session)
    if error:
        session.delete_scan_status["error"] = error
        session.delete_scan_status["done"] = True
        return

    try:
        session.delete_scan_status["message"] = "Fetching emails..."

        query = build_gmail_query(filters)

        results = (
            service.users()
            .messages()
            .list(userId="me", maxResults=min(limit, 500), q=query or None)
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
                    q=query or None,
                )
                .execute()
            )
            messages.extend(results.get("messages", []))

        messages = messages[:limit]
        total = len(messages)

        if total == 0:
            session.delete_scan_status["message"] = "No emails found"
            session.delete_scan_status["done"] = True
            return

        session.delete_scan_status["message"] = f"Scanning {total} emails..."

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
            email_date = None
            for header in headers:
                if header["name"].lower() == "date":
                    email_date = header["value"]
                    break

            if sender_email:
                sender_counts[sender_email]["count"] += 1
                sender_counts[sender_email]["sender"] = sender_name
                sender_counts[sender_email]["email"] = sender_email
                sender_counts[sender_email]["message_ids"].append(msg_id)
                sender_counts[sender_email]["total_size"] += size_estimate
                if len(sender_counts[sender_email]["subjects"]) < 3:
                    sender_counts[sender_email]["subjects"].append(subject)

                # Track first and last dates
                if email_date:
                    if sender_counts[sender_email]["first_date"] is None:
                        sender_counts[sender_email]["first_date"] = email_date
                    sender_counts[sender_email]["last_date"] = email_date

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
            session.delete_scan_status["progress"] = progress
            session.delete_scan_status["message"] = (
                f"Scanned {processed}/{total} emails"
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

        session.delete_scan_results = sorted_senders
        session.delete_scan_status["message"] = f"Found {len(sorted_senders)} senders"
        session.delete_scan_status["done"] = True

    except Exception as e:
        session.delete_scan_status["error"] = str(e)
        session.delete_scan_status["done"] = True


def get_delete_scan_status(session: SessionState) -> dict:
    """Get delete scan status."""
    return session.delete_scan_status.copy()


def get_delete_scan_results(session: SessionState) -> list:
    """Get delete scan results."""
    return session.delete_scan_results.copy()


def delete_emails_by_sender(session: SessionState, sender: str) -> dict:
    """Delete all emails from a specific sender."""
    if not sender or not sender.strip():
        return {
            "success": False,
            "deleted": 0,
            "size_freed": 0,
            "message": "No sender specified",
        }

    # Validate sender format - must be a valid email address or domain
    sender = sender.strip()
    # Email format: user@domain.tld
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    # Domain format: domain.tld (at least one dot, valid domain structure)
    domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$"

    if not (re.match(email_pattern, sender) or re.match(domain_pattern, sender)):
        return {
            "success": False,
            "deleted": 0,
            "size_freed": 0,
            "message": "Invalid sender format. Must be a valid email address or domain.",
        }

    # Get size info from cached results before deleting
    size_freed = 0
    for r in session.delete_scan_results:
        if r.get("email") == sender:
            size_freed = r.get("total_size", 0)
            break

    service, error = get_gmail_service(session)
    if error:
        return {"success": False, "deleted": 0, "size_freed": 0, "message": error}

    try:
        # Find all emails from sender
        query = f"from:{sender}"
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=500)
            .execute()
        )
        messages = results.get("messages", [])

        while "nextPageToken" in results:
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

        if not messages:
            return {
                "success": True,
                "deleted": 0,
                "size_freed": 0,
                "message": "No emails found",
            }

        # Batch delete (move to trash)
        ids = [msg["id"] for msg in messages]
        batch_size = 100
        deleted = 0

        for i in range(0, len(ids), batch_size):
            batch = ids[i : i + batch_size]
            service.users().messages().batchModify(
                userId="me", body={"ids": batch, "addLabelIds": ["TRASH"]}
            ).execute()
            deleted += len(batch)

        # Remove sender from cached results
        session.delete_scan_results = [
            r for r in session.delete_scan_results if r.get("email") != sender
        ]

        return {
            "success": True,
            "deleted": deleted,
            "size_freed": size_freed,
            "message": f"Moved {deleted} emails to trash",
        }

    except Exception as e:
        return {"success": False, "deleted": 0, "size_freed": 0, "message": str(e)}


def delete_emails_bulk(session: SessionState, senders: list[str]) -> dict:
    """Delete emails from multiple senders."""
    if not senders:
        return {
            "success": False,
            "deleted": 0,
            "size_freed": 0,
            "message": "No senders specified",
        }

    total_deleted = 0
    total_size_freed = 0
    errors = []

    for sender in senders:
        result = delete_emails_by_sender(session, sender)
        if result["success"]:
            total_deleted += result["deleted"]
            total_size_freed += result.get("size_freed", 0)
        else:
            errors.append(f"{sender}: {result['message']}")

    # Note: delete_emails_by_sender already removes each sender from cached results

    if errors:
        return {
            "success": len(errors) < len(senders),
            "deleted": total_deleted,
            "size_freed": total_size_freed,
            "message": f"Deleted {total_deleted} emails. Errors: {'; '.join(errors[:3])}",
        }

    if total_deleted == 0:
        return {
            "success": False,
            "deleted": 0,
            "size_freed": 0,
            "message": "No emails found to delete",
        }
    return {
        "success": True,
        "deleted": total_deleted,
        "size_freed": total_size_freed,
        "message": f"Deleted {total_deleted} emails",
    }


def delete_emails_bulk_background(
    session: SessionState, senders: list[str]
) -> None:
    """Delete emails from multiple senders with progress updates (background task).

    Optimized to collect all message IDs first, then batch delete in larger chunks.
    """
    session.reset_delete_bulk()

    # Validate input
    if not senders or not isinstance(senders, list):
        session.delete_bulk_status["done"] = True
        session.delete_bulk_status["error"] = "No senders specified"
        return

    total_senders = len(senders)
    session.delete_bulk_status["total_senders"] = total_senders
    session.delete_bulk_status["message"] = "Collecting emails to delete..."

    service, error = get_gmail_service(session)
    if error:
        session.delete_bulk_status["done"] = True
        session.delete_bulk_status["error"] = error
        return

    # Phase 1: Collect all message IDs from all senders
    all_message_ids = []
    errors = []

    for i, sender in enumerate(senders):
        session.delete_bulk_status["current_sender"] = i + 1
        session.delete_bulk_status["progress"] = int(
            (i / total_senders) * 40
        )  # 0-40% for collecting
        session.delete_bulk_status["message"] = f"Finding emails from {sender}..."

        try:
            query = f"from:{sender}"
            results = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=500)
                .execute()
            )
            messages = results.get("messages", [])

            while "nextPageToken" in results:
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

            all_message_ids.extend([msg["id"] for msg in messages])
        except Exception as e:
            errors.append(f"{sender}: {str(e)}")

    if not all_message_ids:
        session.delete_bulk_status["progress"] = 100
        session.delete_bulk_status["done"] = True
        session.delete_bulk_status["message"] = "No emails found to delete"
        return

    # Phase 2: Batch delete all collected IDs (larger batches = fewer API calls)
    total_emails = len(all_message_ids)
    session.delete_bulk_status["message"] = f"Deleting {total_emails} emails..."

    batch_size = 1000  # Gmail allows up to 1000 per batchModify
    deleted = 0

    try:
        for i in range(0, total_emails, batch_size):
            batch = all_message_ids[i : i + batch_size]
            service.users().messages().batchModify(
                userId="me", body={"ids": batch, "addLabelIds": ["TRASH"]}
            ).execute()
            deleted += len(batch)
            session.delete_bulk_status["deleted_count"] = deleted
            # Progress: 40-100% for deleting
            session.delete_bulk_status["progress"] = 40 + int(
                (deleted / total_emails) * 60
            )
            session.delete_bulk_status["message"] = (
                f"Deleted {deleted}/{total_emails} emails..."
            )
    except Exception as e:
        errors.append(f"Batch delete error: {str(e)}")

    # Remove deleted senders from cached scan results
    session.delete_scan_results = [
        r for r in session.delete_scan_results if r.get("email") not in senders
    ]

    # Done
    session.delete_bulk_status["progress"] = 100
    session.delete_bulk_status["done"] = True
    session.delete_bulk_status["deleted_count"] = deleted

    if errors:
        session.delete_bulk_status["error"] = f"Some errors: {'; '.join(errors[:3])}"
        session.delete_bulk_status["message"] = (
            f"Deleted {deleted} emails with some errors"
        )
    else:
        session.delete_bulk_status["message"] = (
            f"Successfully deleted {deleted} emails"
        )


def get_delete_bulk_status(session: SessionState) -> dict:
    """Get delete bulk operation status."""
    return session.delete_bulk_status.copy()
