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
from app.services.gmail.helpers import (
    build_gmail_query,
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

# Export private helper functions with original names for backward compatibility (tests)
_get_unsubscribe_from_headers = get_unsubscribe_from_headers
_get_sender_info = get_sender_info
_get_subject = get_subject

# Export all public functions
__all__ = [
    # Helpers
    "build_gmail_query",
    # Private helpers (for testing)
    "_get_unsubscribe_from_headers",
    "_get_sender_info",
    "_get_subject",
    # Scanning
    "scan_emails",
    "get_scan_status",
    "get_scan_results",
    # Unsubscribe
    "unsubscribe_single",
    # Mark as read
    "get_unread_count",
    "mark_emails_as_read",
    "get_mark_read_status",
    # Delete
    "scan_senders_for_delete",
    "get_delete_scan_status",
    "get_delete_scan_results",
    "delete_emails_by_sender",
    "delete_emails_bulk",
    "delete_emails_bulk_background",
    "get_delete_bulk_status",
    # Download
    "download_emails_background",
    "get_download_status",
    "get_download_csv",
    # Labels
    "get_labels",
    "create_label",
    "delete_label",
    "apply_label_to_senders_background",
    "remove_label_from_senders_background",
    "get_label_operation_status",
    # Archive
    "archive_emails_background",
    "get_archive_status",
    # Mark Important
    "mark_important_background",
    "get_important_status",
]
