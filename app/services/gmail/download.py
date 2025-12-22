"""
Gmail Download Operations
-------------------------
Functions for downloading email metadata as CSV.
"""

import base64
import csv
import io
import time

from app.core import state
from app.services.auth import get_gmail_service


def download_emails_background(senders: list[str]) -> None:
    """Download email metadata for selected senders as CSV (background task).

    Uses message IDs stored during scan to download only scanned emails.
    """
    state.reset_download()

    # Validate input
    if not senders or not isinstance(senders, list):
        state.download_status["done"] = True
        state.download_status["error"] = "No senders specified"
        return

    service, error = get_gmail_service()
    if error:
        state.download_status["done"] = True
        state.download_status["error"] = error
        return

    state.download_status["message"] = "Collecting emails from scan results..."

    # Get message IDs from scan results (only emails we actually scanned)
    all_message_ids = []
    for sender in senders:
        for result in state.delete_scan_results:
            if result.get("email") == sender:
                all_message_ids.extend(result.get("message_ids", []))
                break

    if not all_message_ids:
        state.download_status["progress"] = 100
        state.download_status["done"] = True
        state.download_status["error"] = "No emails found in scan results"
        return

    total_emails = len(all_message_ids)
    state.download_status["total_emails"] = total_emails
    state.download_status["message"] = f"Fetching {total_emails} emails..."

    # Helper to decode base64 email content
    def decode_base64_content(data: str) -> str:
        """Decode base64 URL-safe encoded email content."""
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    # Helper function to extract email body
    def get_email_body(payload) -> str:
        """Extract email body from payload. Prefers text/plain over text/html."""
        body = ""

        if "body" in payload and payload["body"].get("data"):
            body = decode_base64_content(payload["body"]["data"])
        elif "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain":
                    if "body" in part and part["body"].get("data"):
                        body = decode_base64_content(part["body"]["data"])
                        break
                elif mime_type == "text/html" and not body:
                    if "body" in part and part["body"].get("data"):
                        body = decode_base64_content(part["body"]["data"])
                elif "parts" in part:
                    body = get_email_body(part)
                    if body:
                        break

        return body.strip()

    # Fetch full email content in batches
    email_data = []
    batch_size = 50  # Smaller batches for full content
    fetched = 0

    try:
        for i in range(0, total_emails, batch_size):
            batch_ids = all_message_ids[i : i + batch_size]

            batch = service.new_batch_http_request()
            batch_results = []

            def callback(
                _request_id, response, exception, results=batch_results
            ) -> None:
                if exception is None and response:
                    results.append(response)

            for msg_id in batch_ids:
                batch.add(
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full"),
                    callback=callback,
                )

            batch.execute()

            # Process batch results
            for msg in batch_results:
                headers = {
                    h["name"]: h["value"]
                    for h in msg.get("payload", {}).get("headers", [])
                }
                body = get_email_body(msg.get("payload", {}))

                email_data.append(
                    {
                        "message_id": msg.get("id", ""),
                        "thread_id": msg.get("threadId", ""),
                        "from": headers.get("From", ""),
                        "subject": headers.get("Subject", ""),
                        "date": headers.get("Date", ""),
                        "labels": ", ".join(msg.get("labelIds", [])),
                        "snippet": msg.get("snippet", "")[:100],
                        "body": (
                            body[:50000] if body else ""
                        ),  # Limit to 50,000 characters
                    }
                )

            fetched += len(batch_ids)
            state.download_status["fetched_count"] = fetched
            state.download_status["progress"] = int((fetched / total_emails) * 95)
            state.download_status["message"] = (
                f"Fetched {fetched}/{total_emails} emails..."
            )

            # Rate limiting: sleep every 5 batches to avoid hitting API limits
            if (i // batch_size + 1) % 5 == 0:
                time.sleep(0.3)

    except Exception as e:
        state.download_status["done"] = True
        state.download_status["error"] = f"Error fetching emails: {str(e)}"
        return

    # Generate CSV
    state.download_status["progress"] = 98
    state.download_status["message"] = "Generating CSV..."

    try:
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "message_id",
                "thread_id",
                "from",
                "subject",
                "date",
                "labels",
                "snippet",
                "body",
            ],
        )
        writer.writeheader()
        writer.writerows(email_data)

        state.download_status["csv_data"] = output.getvalue()
        state.download_status["progress"] = 100
        state.download_status["done"] = True
        state.download_status["message"] = f"Ready to download {len(email_data)} emails"

    except Exception as e:
        state.download_status["done"] = True
        state.download_status["error"] = f"Error generating CSV: {str(e)}"


def get_download_status() -> dict:
    """Get download operation status (without CSV data)."""
    return {
        "progress": state.download_status["progress"],
        "message": state.download_status["message"],
        "done": state.download_status["done"],
        "error": state.download_status["error"],
        "total_emails": state.download_status["total_emails"],
        "fetched_count": state.download_status["fetched_count"],
    }


def get_download_csv() -> str | None:
    """Get the generated CSV data."""
    return state.download_status.get("csv_data")
