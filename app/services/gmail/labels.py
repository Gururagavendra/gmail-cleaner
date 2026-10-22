"""
Gmail Label Management Operations
----------------------------------
Functions for managing Gmail labels.
"""

from app.core import state
from app.services.auth import get_gmail_service
from app.services.gmail.helpers import sanitize_gmail_query_value


def get_labels() -> dict:
    """Get all Gmail labels."""
    service, error = get_gmail_service()
    if error:
        return {"success": False, "labels": [], "error": error}

    try:
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        # Categorize labels
        system_labels = []
        user_labels = []

        for label in labels:
            label_info = {
                "id": label.get("id"),
                "name": label.get("name"),
                "type": label.get("type", "user"),
            }

            if label.get("type") == "system":
                system_labels.append(label_info)
            else:
                user_labels.append(label_info)

        # Sort user labels alphabetically
        user_labels.sort(key=lambda x: x["name"].lower())

        return {
            "success": True,
            "system_labels": system_labels,
            "user_labels": user_labels,
            "error": None,
        }
    except Exception as e:
        return {"success": False, "labels": [], "error": str(e)}


def create_label(name: str) -> dict:
    """Create a new Gmail label."""
    if not name or not name.strip():
        return {"success": False, "label": None, "error": "Label name is required"}

    service, error = get_gmail_service()
    if error:
        return {"success": False, "label": None, "error": error}

    try:
        label_body = {
            "name": name.strip(),
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }

        result = service.users().labels().create(userId="me", body=label_body).execute()

        return {
            "success": True,
            "label": {
                "id": result.get("id"),
                "name": result.get("name"),
                "type": result.get("type", "user"),
            },
            "error": None,
        }
    except Exception as e:
        error_msg = str(e)
        if "Label name exists" in error_msg or "already exists" in error_msg.lower():
            return {
                "success": False,
                "label": None,
                "error": "A label with this name already exists",
            }
        return {"success": False, "label": None, "error": error_msg}


def delete_label(label_id: str) -> dict:
    """Delete a Gmail label."""
    if not label_id:
        return {"success": False, "error": "Label ID is required"}

    service, error = get_gmail_service()
    if error:
        return {"success": False, "error": error}

    try:
        service.users().labels().delete(userId="me", id=label_id).execute()
        return {"success": True, "error": None}
    except Exception as e:
        error_msg = str(e)
        if "Not Found" in error_msg:
            return {"success": False, "error": "Label not found"}
        if "Cannot delete" in error_msg or "system label" in error_msg.lower():
            return {"success": False, "error": "Cannot delete system labels"}
        return {"success": False, "error": error_msg}


def _apply_label_operation_background(
    label_id: str,
    senders: list[str],
    *,
    add_label: bool,
    finding_message: str,
    applying_message: str,
    no_emails_message: str,
    progress_message_template: str,
    success_message_template: str,
    error_message_template: str,
) -> None:
    """Common helper for applying or removing labels from senders (background task).

    Args:
        label_id: The label ID to apply or remove
        senders: List of sender email addresses or domains
        add_label: If True, add the label; if False, remove it
        finding_message: Message to show while finding emails
        applying_message: Message to show while applying operation
        no_emails_message: Message when no emails found
        progress_message_template: Template for progress updates (use {count} and {total})
        success_message_template: Template for success message (use {count})
        error_message_template: Template for error message (use {count})
    """
    state.reset_label_operation()

    if not label_id or not label_id.strip():
        state.update_label_operation_status(done=True, error="Label ID is required")
        return

    # Validate input
    if not senders or not isinstance(senders, list):
        state.update_label_operation_status(done=True, error="No senders specified")
        return

    service, error = get_gmail_service()
    if error:
        state.update_label_operation_status(done=True, error=error)
        return

    total_senders = len(senders)
    state.update_label_operation_status(
        total_senders=total_senders, message=finding_message
    )

    # Phase 1: Collect all message IDs
    all_message_ids = []
    errors = []
    label_name = None

    # For remove operations, we need the label name for the query
    # Fetch it once before processing senders
    if not add_label:
        try:
            label_info = (
                service.users().labels().get(userId="me", id=label_id).execute()
            )
            label_name = label_info.get("name", "")
            if not label_name:
                state.update_label_operation_status(
                    done=True, error="Could not get label name"
                )
                return
        except Exception as e:
            state.update_label_operation_status(
                done=True, error=f"Failed to fetch label: {e!s}"
            )
            return

    for i, sender in enumerate(senders):
        progress = int((i / total_senders) * 40)
        state.update_label_operation_status(
            current_sender=i + 1,
            progress=progress,
            message=f"Finding emails from {sender}...",
        )

        try:
            # Build query: for remove, include label filter; for add, just sender
            if add_label:
                query = f"from:{sanitize_gmail_query_value(sender)}"
            else:
                query = f"from:{sanitize_gmail_query_value(sender)} label:{label_name}"

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
            errors.append(f"{sender}: {e!s}")

    if not all_message_ids:
        state.update_label_operation_status(
            progress=100, done=True, message=no_emails_message
        )
        return

    # Phase 2: Apply/remove label in batches
    total_emails = len(all_message_ids)
    state.update_label_operation_status(
        message=applying_message.format(count=total_emails)
    )

    batch_size = 1000
    affected = 0

    # Build batch modify body
    if add_label:
        body_template = {"ids": None, "addLabelIds": [label_id]}
    else:
        body_template = {"ids": None, "removeLabelIds": [label_id]}

    try:
        for i in range(0, total_emails, batch_size):
            batch = all_message_ids[i : i + batch_size]
            body = {**body_template, "ids": batch}
            service.users().messages().batchModify(userId="me", body=body).execute()
            affected += len(batch)
            progress = 40 + int((affected / total_emails) * 60)
            state.update_label_operation_status(
                affected_count=affected,
                progress=progress,
                message=progress_message_template.format(count=affected, total=total_emails),
            )
    except Exception as e:
        errors.append(f"Batch operation error: {e!s}")

    # Done
    if errors:
        state.update_label_operation_status(
            progress=100,
            done=True,
            affected_count=affected,
            error=f"Some errors: {'; '.join(errors[:3])}",
            message=error_message_template.format(count=affected),
        )
    else:
        state.update_label_operation_status(
            progress=100,
            done=True,
            affected_count=affected,
            message=success_message_template.format(count=affected),
        )


def apply_label_to_senders_background(label_id: str, senders: list[str]) -> None:
    """Apply a label to all emails from specified senders (background task)."""
    _apply_label_operation_background(
        label_id=label_id,
        senders=senders,
        add_label=True,
        finding_message="Finding emails to label...",
        applying_message="Applying label to {count} emails...",
        no_emails_message="No emails found to label",
        progress_message_template="Labeled {count}/{total} emails...",
        success_message_template="Successfully labeled {count} emails",
        error_message_template="Labeled {count} emails with some errors",
    )


def remove_label_from_senders_background(label_id: str, senders: list[str]) -> None:
    """Remove a label from all emails from specified senders (background task)."""
    _apply_label_operation_background(
        label_id=label_id,
        senders=senders,
        add_label=False,
        finding_message="Finding emails to unlabel...",
        applying_message="Removing label from {count} emails...",
        no_emails_message="No emails found with this label",
        progress_message_template="Unlabeled {count}/{total} emails...",
        success_message_template="Successfully removed label from {count} emails",
        error_message_template="Unlabeled {count} emails with some errors",
    )


def get_label_operation_status() -> dict:
    """Get label operation status."""
    return state.label_operation_status.copy()
