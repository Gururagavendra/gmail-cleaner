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
)
