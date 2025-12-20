"""
Gmail Label Management Operations
----------------------------------
Functions for managing Gmail labels.
"""

from app.core import state
from app.services.auth import get_gmail_service


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


def apply_label_to_senders_background(label_id: str, senders: list[str]) -> None:
    """Apply a label to all emails from specified senders (background task)."""
    state.reset_label_operation()

    if not label_id or not label_id.strip():
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = "Label ID is required"
        return

    # Validate input
    if not senders or not isinstance(senders, list):
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = "No senders specified"
        return

    service, error = get_gmail_service()
    if error:
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = error
        return

    total_senders = len(senders)
    state.label_operation_status["total_senders"] = total_senders
    state.label_operation_status["message"] = "Finding emails to label..."

    # Phase 1: Collect all message IDs
    all_message_ids = []
    errors = []

    for i, sender in enumerate(senders):
        state.label_operation_status["current_sender"] = i + 1
        state.label_operation_status["progress"] = int((i / total_senders) * 40)
        state.label_operation_status["message"] = f"Finding emails from {sender}..."

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
        state.label_operation_status["progress"] = 100
        state.label_operation_status["done"] = True
        state.label_operation_status["message"] = "No emails found to label"
        return

    # Phase 2: Apply label in batches
    total_emails = len(all_message_ids)
    state.label_operation_status["message"] = (
        f"Applying label to {total_emails} emails..."
    )

    batch_size = 1000
    labeled = 0

    try:
        for i in range(0, total_emails, batch_size):
            batch = all_message_ids[i : i + batch_size]
            service.users().messages().batchModify(
                userId="me", body={"ids": batch, "addLabelIds": [label_id]}
            ).execute()
            labeled += len(batch)
            state.label_operation_status["affected_count"] = labeled
            state.label_operation_status["progress"] = 40 + int(
                (labeled / total_emails) * 60
            )
            state.label_operation_status["message"] = (
                f"Labeled {labeled}/{total_emails} emails..."
            )
    except Exception as e:
        errors.append(f"Batch label error: {str(e)}")

    # Done
    state.label_operation_status["progress"] = 100
    state.label_operation_status["done"] = True
    state.label_operation_status["affected_count"] = labeled

    if errors:
        state.label_operation_status["error"] = f"Some errors: {'; '.join(errors[:3])}"
        state.label_operation_status["message"] = (
            f"Labeled {labeled} emails with some errors"
        )
    else:
        state.label_operation_status["message"] = (
            f"Successfully labeled {labeled} emails"
        )


def remove_label_from_senders_background(label_id: str, senders: list[str]) -> None:
    """Remove a label from all emails from specified senders (background task)."""
    state.reset_label_operation()

    if not label_id or not label_id.strip():
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = "Label ID is required"
        return

    # Validate input
    if not senders or not isinstance(senders, list):
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = "No senders specified"
        return

    service, error = get_gmail_service()
    if error:
        state.label_operation_status["done"] = True
        state.label_operation_status["error"] = error
        return

    total_senders = len(senders)
    state.label_operation_status["total_senders"] = total_senders
    state.label_operation_status["message"] = "Finding emails to unlabel..."

    # Phase 1: Collect all message IDs that have this label
    all_message_ids = []
    errors = []

    for i, sender in enumerate(senders):
        state.label_operation_status["current_sender"] = i + 1
        state.label_operation_status["progress"] = int((i / total_senders) * 40)
        state.label_operation_status["message"] = f"Finding emails from {sender}..."

        try:
            # Search for emails from sender that have this label
            query = f"from:{sender} label:{label_id}"
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
        state.label_operation_status["progress"] = 100
        state.label_operation_status["done"] = True
        state.label_operation_status["message"] = "No emails found with this label"
        return

    # Phase 2: Remove label in batches
    total_emails = len(all_message_ids)
    state.label_operation_status["message"] = (
        f"Removing label from {total_emails} emails..."
    )

    batch_size = 1000
    unlabeled = 0

    try:
        for i in range(0, total_emails, batch_size):
            batch = all_message_ids[i : i + batch_size]
            service.users().messages().batchModify(
                userId="me", body={"ids": batch, "removeLabelIds": [label_id]}
            ).execute()
            unlabeled += len(batch)
            state.label_operation_status["affected_count"] = unlabeled
            state.label_operation_status["progress"] = 40 + int(
                (unlabeled / total_emails) * 60
            )
            state.label_operation_status["message"] = (
                f"Unlabeled {unlabeled}/{total_emails} emails..."
            )
    except Exception as e:
        errors.append(f"Batch unlabel error: {str(e)}")

    # Done
    state.label_operation_status["progress"] = 100
    state.label_operation_status["done"] = True
    state.label_operation_status["affected_count"] = unlabeled

    if errors:
        state.label_operation_status["error"] = f"Some errors: {'; '.join(errors[:3])}"
        state.label_operation_status["message"] = (
            f"Unlabeled {unlabeled} emails with some errors"
        )
    else:
        state.label_operation_status["message"] = (
            f"Successfully removed label from {unlabeled} emails"
        )


def get_label_operation_status() -> dict:
    """Get label operation status."""
    return state.label_operation_status.copy()
