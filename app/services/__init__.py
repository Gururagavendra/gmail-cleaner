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
)

from .ai_longtail import (
    get_ai_config_status,
    save_ai_config,
    classify_one_long_tail_email,
    scan_long_tail_candidates,
    get_long_tail_scan_status,
    get_long_tail_scan_results,
    classify_long_tail_candidates_background,
    cancel_long_tail_classification,
    get_long_tail_classify_status,
    get_long_tail_classify_results,
    apply_long_tail_actions_background,
    get_long_tail_apply_status,
)
