"""
Gmail Service Module
---------------------
Core Gmail operations: scanning, unsubscribing, marking read, deleting.

This module is split into multiple files for better organization:
- helpers.py: Security, filters, and email parsing utilities
- scan.py: Email scanning operations
- unsubscribe.py: Unsubscribe operations
- mark_read.py: Mark as read operations
- delete.py: Delete operations
- download.py: Email download operations
- labels.py: Label management operations
- archive.py: Archive operations
- important.py: Mark important operations
"""

# Import all functions for backward compatibility
from app.services.auth import get_gmail_service
from app.services.gmail.helpers import (
    build_gmail_query,
    sanitize_gmail_query_value,
    validate_unsafe_url,
    get_unsubscribe_from_headers,
    get_sender_info,
    get_subject,
)
from app.services.gmail.scan import (
    scan_emails,
    get_scan_status,
    get_scan_results,
)
from app.services.gmail.unsubscribe import (
    unsubscribe_single,
)
from app.services.gmail.mark_read import (
    get_unread_count,
    mark_emails_as_read,
    get_mark_read_status,
)
from app.services.gmail.delete import (
    scan_senders_for_delete,
    get_delete_scan_status,
    get_delete_scan_results,
    delete_emails_by_sender,
    delete_emails_bulk,
    delete_emails_bulk_background,
    get_delete_bulk_status,
)
from app.services.gmail.download import (
    download_emails_background,
    get_download_status,
    get_download_csv,
)
from app.services.gmail.labels import (
    get_labels,
    create_label,
    delete_label,
    apply_label_to_senders_background,
    remove_label_from_senders_background,
    get_label_operation_status,
)
from app.services.gmail.archive import (
    archive_emails_background,
    get_archive_status,
)
from app.services.gmail.important import (
    mark_important_background,
    get_important_status,
)
from app.services.gmail.unread import (
    scan_unread_by_sender,
    get_unread_scan_status,
    get_unread_scan_results,
    get_unread_action_status,
    mark_read_by_senders_background,
    mark_read_and_archive_by_senders_background,
    archive_unread_by_senders_background,
    delete_unread_by_senders_background,
)

# Export private helper functions with underscore-prefixed aliases for backward compatibility.
# These are used by tests that import the original function names from this module.
_get_unsubscribe_from_headers = get_unsubscribe_from_headers
_get_sender_info = get_sender_info
_get_subject = get_subject

# Export all public functions
__all__ = [
    # Archive
    "archive_emails_background",
    "get_archive_status",
    # Auth (for backward compatibility)
    "get_gmail_service",
    # Delete
    "delete_emails_bulk",
    "delete_emails_bulk_background",
    "delete_emails_by_sender",
    "get_delete_bulk_status",
    "get_delete_scan_results",
    "get_delete_scan_status",
    "scan_senders_for_delete",
    # Download
    "download_emails_background",
    "get_download_csv",
    "get_download_status",
    # Helpers
    "build_gmail_query",
    "sanitize_gmail_query_value",
    "validate_unsafe_url",
    # Important
    "get_important_status",
    "mark_important_background",
    # Labels
    "apply_label_to_senders_background",
    "create_label",
    "delete_label",
    "get_label_operation_status",
    "get_labels",
    "remove_label_from_senders_background",
    # Mark as read
    "get_mark_read_status",
    "get_unread_count",
    "mark_emails_as_read",
    # Private helpers (for testing)
    "_get_sender_info",
    "_get_subject",
    "_get_unsubscribe_from_headers",
    # Scanning
    "get_scan_results",
    "get_scan_status",
    "scan_emails",
    # Unsubscribe
    "unsubscribe_single",
    # Unread
    "archive_unread_by_senders_background",
    "delete_unread_by_senders_background",
    "get_unread_action_status",
    "get_unread_scan_results",
    "get_unread_scan_status",
    "mark_read_and_archive_by_senders_background",
    "mark_read_by_senders_background",
    "scan_unread_by_sender",
]
