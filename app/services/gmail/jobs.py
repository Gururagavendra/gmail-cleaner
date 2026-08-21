"""
Gmail Job Operations
--------------------
Long-running bulk email operations with cancellation support.
Iterates through ALL matching emails, respects API rate limits.
"""

import logging
import time
from collections import defaultdict
from email.utils import parsedate_to_datetime
from typing import Optional

from googleapiclient.errors import HttpError

from app.core import state
from app.services.auth import get_gmail_service
from app.services.gmail.helpers import (
    build_gmail_query,
    get_unsubscribe_from_headers,
    get_sender_info,
    get_subject,
)

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"search", "delete", "archive", "label", "mark_important", "find_subscriptions"}

# Max message IDs stored per sender in find_subscriptions results.
# Beyond this the sender is high-volume; domain-wide delete is more appropriate.
_MAX_IDS_PER_SENDER = 500

_BACKOFF_BASE = 2  # seconds; doubles each retry
_BACKOFF_MAX_RETRIES = 6  # max ~64 s wait before giving up


def _is_rate_limit(e: HttpError) -> bool:
    if e.resp.status not in (403, 429):
        return False
    try:
        import json
        details = json.loads(e.content).get("error", {}).get("errors", [{}])
        reason = details[0].get("reason", "")
        return reason in ("rateLimitExceeded", "userRateLimitExceeded") or e.resp.status == 429
    except Exception:
        return e.resp.status == 429


def _execute(request):
    """Execute a Gmail API request with exponential backoff on rate-limit errors."""
    wait = _BACKOFF_BASE
    for attempt in range(_BACKOFF_MAX_RETRIES):
        try:
            return request.execute()
        except HttpError as e:
            if _is_rate_limit(e):
                logger.warning("Rate limit hit, backing off %ds (attempt %d)", wait, attempt + 1)
                state.job_status["message"] = f"Rate limit hit — waiting {wait}s before retrying..."
                time.sleep(wait)
                wait = min(wait * 2, 64)
                continue
            raise
    return request.execute()  # final attempt, let it raise


def _execute_batch(batch):
    """Execute a Gmail batch HTTP request with exponential backoff."""
    wait = _BACKOFF_BASE
    for attempt in range(_BACKOFF_MAX_RETRIES):
        try:
            return batch.execute()
        except HttpError as e:
            if _is_rate_limit(e):
                logger.warning("Rate limit hit on batch, backing off %ds (attempt %d)", wait, attempt + 1)
                state.job_status["message"] = f"Rate limit hit — waiting {wait}s before retrying..."
                time.sleep(wait)
                wait = min(wait * 2, 64)
                continue
            raise
    return batch.execute()


def run_job(
    action: str,
    filters: Optional[dict] = None,
    label_id: Optional[str] = None,
    important: bool = True,
    mailbox: Optional[str] = None,
):
    """Run a long-running bulk email job with cancellation support.

    Iterates through ALL emails matching the filters page by page,
    applying the specified action in batches of 100 (batchModify limit).
    Checks cancellation flag before each batch and between pages.
    """
    # Slot already claimed (running=True) by the API handler before add_task().
    # Just set the remaining fields without resetting running.
    state.job_status["action"] = action
    state.job_status["message"] = "Connecting to Gmail... (intentionally throttled to avoid API rate limits)"

    if action not in VALID_ACTIONS:
        state.job_status["error"] = f"Invalid action: {action}"
        state.job_status["done"] = True
        state.job_status["running"] = False
        return

    if action == "label" and not label_id:
        state.job_status["error"] = "label_id is required for the 'label' action"
        state.job_status["done"] = True
        state.job_status["running"] = False
        return

    service, error = get_gmail_service()
    if error:
        state.job_status["error"] = error
        state.job_status["done"] = True
        state.job_status["running"] = False
        return

    try:
        query = build_gmail_query(filters)
        state.job_status["message"] = f"Starting '{action}' job... (throttled ~1s/batch to avoid Gmail API rate limits)"

        def base_list_params(include_spam_trash: bool = False) -> dict:
            params: dict = {"userId": "me", "maxResults": 500}
            if query:
                params["q"] = query
            if mailbox:
                params["labelIds"] = [mailbox]
            if include_spam_trash or mailbox in ("SPAM", "TRASH"):
                params["includeSpamTrash"] = True
            return params

        if action == "find_subscriptions":
            _run_find_subscriptions(service, query, mailbox=mailbox)
            if state.job_status["cancelled"]:
                state.job_status["message"] = (
                    f"Cancelled. Found {len(state.scan_results)} subscriptions so far."
                )
            else:
                state.job_status["progress"] = 100
                state.job_status["message"] = (
                    f"Done! Found {len(state.scan_results)} subscriptions."
                )
            state.job_status["done"] = True
            state.job_status["running"] = False
            return

        if action == "search":
            page_token = None
            pages = 0
            total = 0
            while True:
                if state.job_status["cancelled"]:
                    break
                list_params = base_list_params(include_spam_trash=True)
                if page_token:
                    list_params["pageToken"] = page_token
                result = _execute(service.users().messages().list(**list_params))
                messages = result.get("messages", [])
                if not messages:
                    break
                pages += 1
                total += len(messages)
                state.job_status["batches_processed"] = pages
                state.job_status["emails_affected"] = total
                state.job_status["message"] = f"Page {pages}: {total} emails found so far (throttled to avoid rate limits)..."
                page_token = result.get("nextPageToken")
                if not page_token:
                    break
                time.sleep(1.0)

            if state.job_status["cancelled"]:
                state.job_status["message"] = f"Cancelled. Found {total} emails so far."
            else:
                state.job_status["progress"] = 100
                state.job_status["message"] = f"Done! Found {total} emails matching your filters."
            state.job_status["done"] = True
            state.job_status["running"] = False
            return

        page_token = None
        batches_processed = 0
        emails_affected = 0
        page_num = 0

        while True:
            # Check cancellation before listing next page
            if state.job_status["cancelled"]:
                break

            # List next page of messages
            list_params = base_list_params()
            if page_token:
                list_params["pageToken"] = page_token

            result = _execute(service.users().messages().list(**list_params))
            messages = result.get("messages", [])

            if not messages:
                break

            message_ids = [m["id"] for m in messages]
            page_num += 1
            state.job_status["message"] = (
                f"Page {page_num}: processing {len(message_ids)} emails..."
            )

            # Apply action in sub-batches of 100 (batchModify limit)
            for i in range(0, len(message_ids), 100):
                if state.job_status["cancelled"]:
                    break

                sub_batch = message_ids[i : i + 100]

                if action == "delete":
                    _execute(service.users().messages().batchModify(
                        userId="me",
                        body={"ids": sub_batch, "addLabelIds": ["TRASH"]},
                    ))
                elif action == "archive":
                    _execute(service.users().messages().batchModify(
                        userId="me",
                        body={"ids": sub_batch, "removeLabelIds": ["INBOX"]},
                    ))
                elif action == "label":
                    _execute(service.users().messages().batchModify(
                        userId="me",
                        body={"ids": sub_batch, "addLabelIds": [label_id]},
                    ))
                elif action == "mark_important":
                    if important:
                        body = {"ids": sub_batch, "addLabelIds": ["IMPORTANT"]}
                    else:
                        body = {"ids": sub_batch, "removeLabelIds": ["IMPORTANT"]}
                    _execute(service.users().messages().batchModify(
                        userId="me", body=body
                    ))

                batches_processed += 1
                emails_affected += len(sub_batch)
                state.job_status["batches_processed"] = batches_processed
                state.job_status["emails_affected"] = emails_affected
                state.job_status["message"] = (
                    f"Batch {batches_processed}: {emails_affected} emails affected "
                    f"(throttled to avoid rate limits)..."
                )

                # Rate limit: pause 1s between every batchModify call
                time.sleep(1.0)

            if state.job_status["cancelled"]:
                break

            page_token = result.get("nextPageToken")
            if not page_token:
                break

            # Pause between list pages to stay under Gmail quota limits
            time.sleep(2.0)

        if state.job_status["cancelled"]:
            state.job_status["message"] = (
                f"Cancelled. Affected {emails_affected} emails "
                f"in {batches_processed} batches."
            )
        else:
            state.job_status["progress"] = 100
            state.job_status["message"] = (
                f"Done! Affected {emails_affected} emails "
                f"in {batches_processed} batches."
            )

        state.job_status["done"] = True
        state.job_status["running"] = False

    except Exception as e:
        logger.exception("Error running job")
        state.job_status["error"] = str(e)
        state.job_status["done"] = True
        state.job_status["running"] = False


def _run_find_subscriptions(service, query: str, mailbox: Optional[str] = None) -> None:
    """Scan ALL matching emails for unsubscribe links, populating state.scan_results."""
    state.reset_scan()
    state.scan_status["message"] = "Scanning for subscriptions (throttled ~1s/batch to avoid Gmail API rate limits)..."

    unsubscribe_data: dict[str, dict] = defaultdict(
        lambda: {
            "link": None,
            "count": 0,
            "subjects": [],
            "type": None,
            "sender": "",
            "email": "",
            "first_date": None,
            "last_date": None,
            "message_ids": [],
        }
    )

    batches_processed = 0
    emails_scanned = 0
    page_token = None

    def process_message(request_id, response, exception) -> None:
        nonlocal emails_scanned
        emails_scanned += 1
        if exception or not response:
            return

        headers = response.get("payload", {}).get("headers", [])
        unsub_link, unsub_type = get_unsubscribe_from_headers(headers)
        if not unsub_link:
            return

        sender_name, sender_email = get_sender_info(headers)
        subject = get_subject(headers)
        domain = sender_email.split("@")[-1] if "@" in sender_email else sender_email
        msg_id = response.get("id", "")
        email_date = next(
            (h["value"] for h in headers if h["name"].lower() == "date"), None
        )

        unsubscribe_data[domain]["link"] = unsub_link
        unsubscribe_data[domain]["count"] += 1
        unsubscribe_data[domain]["type"] = unsub_type
        unsubscribe_data[domain]["sender"] = sender_name
        unsubscribe_data[domain]["email"] = sender_email
        if msg_id and len(unsubscribe_data[domain]["message_ids"]) < _MAX_IDS_PER_SENDER:
            unsubscribe_data[domain]["message_ids"].append(msg_id)
        if len(unsubscribe_data[domain]["subjects"]) < 3:
            unsubscribe_data[domain]["subjects"].append(subject)

        if email_date:
            try:
                msg_dt = parsedate_to_datetime(email_date)
                for field, comparator in (("first_date", lambda a, b: a < b), ("last_date", lambda a, b: a > b)):
                    current = unsubscribe_data[domain][field]
                    if current is None:
                        unsubscribe_data[domain][field] = email_date
                    else:
                        try:
                            if comparator(msg_dt, parsedate_to_datetime(current)):
                                unsubscribe_data[domain][field] = email_date
                        except (ValueError, TypeError):
                            pass
            except (ValueError, TypeError):
                pass

    while True:
        if state.job_status["cancelled"]:
            break

        list_params: dict = {"userId": "me", "maxResults": 500}
        if page_token:
            list_params["pageToken"] = page_token
        if query:
            list_params["q"] = query
        if mailbox:
            list_params["labelIds"] = [mailbox]

        result = _execute(service.users().messages().list(**list_params))
        messages = result.get("messages", [])
        if not messages:
            break

        message_ids = [m["id"] for m in messages]

        for i in range(0, len(message_ids), 100):
            if state.job_status["cancelled"]:
                break

            sub_batch = message_ids[i : i + 100]
            batch = service.new_batch_http_request(callback=process_message)
            for msg_id in sub_batch:
                batch.add(
                    service.users().messages().get(
                        userId="me",
                        id=msg_id,
                        format="metadata",
                        metadataHeaders=["From", "Subject", "Date", "List-Unsubscribe", "List-Unsubscribe-Post"],
                    )
                )
            _execute_batch(batch)

            batches_processed += 1
            state.job_status["batches_processed"] = batches_processed
            state.job_status["emails_affected"] = len(unsubscribe_data)
            state.job_status["message"] = (
                f"Batch {batches_processed}: scanned ~{emails_scanned} emails, "
                f"found {len(unsubscribe_data)} senders (throttled to avoid rate limits)..."
            )

            # Sleep 1s between every batch of 100 metadata fetches to stay under quota
            time.sleep(1.0)

        if state.job_status["cancelled"]:
            break

        page_token = result.get("nextPageToken")
        if not page_token:
            break

        time.sleep(2.0)

    # Write results to scan state so the Unsubscribe view can display them
    sorted_results = sorted(
        [
            {
                "domain": k,
                "link": v["link"],
                "count": v["count"],
                "subjects": v["subjects"],
                "type": v["type"],
                "sender": v.get("sender", ""),
                "email": v.get("email", ""),
                "first_date": v.get("first_date"),
                "last_date": v.get("last_date"),
                "message_ids": v.get("message_ids", []),
            }
            for k, v in unsubscribe_data.items()
        ],
        key=lambda x: x.get("count", 0) or 0,
        reverse=True,
    )
    state.scan_results = sorted_results
    state.scan_status["done"] = True
    state.scan_status["message"] = f"Found {len(sorted_results)} subscriptions"


def cancel_job() -> dict:
    """Request cancellation of the current running job."""
    if state.job_status["running"]:
        state.job_status["cancelled"] = True
        state.job_status["message"] = "Cancelling..."
    return state.job_status.copy()


def get_job_status() -> dict:
    """Get current job status."""
    return state.job_status.copy()
