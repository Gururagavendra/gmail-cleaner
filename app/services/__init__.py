"""Services module exports."""

from .auth import (
    get_gmail_service,
    sign_out,
    check_login_status,
    get_web_auth_status,
    is_web_auth_mode,
    needs_auth_setup,
)

from .gmail import (
    # Filters
    build_gmail_query,
    # Scanning
    scan_emails,
    get_scan_status,
    get_scan_results,
    # Unsubscribe
    unsubscribe_single,
    # Mark as read
    get_unread_count,
    mark_emails_as_read,
    get_mark_read_status,
    # Delete
    scan_senders_for_delete,
    get_delete_scan_status,
    get_delete_scan_results,
    delete_emails_by_sender,
    delete_emails_bulk,
    delete_emails_bulk_background,
    get_delete_bulk_status,
    # Download
    download_emails_background,
    get_download_status,
    get_download_csv,
    # Labels
    get_labels,
    create_label,
    delete_label,
    apply_label_to_senders_background,
    remove_label_from_senders_background,
    get_label_operation_status,
    # Archive
    archive_emails_background,
    get_archive_status,
    # Mark Important
    mark_important_background,
    get_important_status,
    # Unread
    scan_unread_by_sender,
    get_unread_scan_status,
    get_unread_scan_results,
    get_unread_action_status,
    mark_read_by_senders_background,
    mark_read_and_archive_by_senders_background,
    archive_unread_by_senders_background,
    delete_unread_by_senders_background,
)
