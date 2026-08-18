"""
Actions API Routes
------------------
POST endpoints for triggering operations.

Rate limits:
- Auth endpoints: 10 requests/minute
- Action endpoints: 30 requests/minute
- Heavy operations (scan, delete): 10 requests/minute
"""

import logging
from functools import partial
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.core.rate_limit import (
    limiter,
    ACTION_RATE_LIMIT,
    AUTH_RATE_LIMIT,
    HEAVY_OPERATION_RATE_LIMIT,
)
from app.models import (
    ScanRequest,
    MarkReadRequest,
    DeleteScanRequest,
    UnsubscribeRequest,
    DeleteEmailsRequest,
    DeleteBulkRequest,
    DownloadEmailsRequest,
    CreateLabelRequest,
    ApplyLabelRequest,
    RemoveLabelRequest,
    ArchiveRequest,
    MarkImportantRequest,
    UnreadScanRequest,
    UnreadActionRequest,
)
from app.services import (
    scan_emails,
    get_gmail_service,
    sign_out,
    unsubscribe_single,
    mark_emails_as_read,
    scan_senders_for_delete,
    delete_emails_by_sender,
    delete_emails_bulk_background,
    download_emails_background,
    create_label,
    delete_label,
    apply_label_to_senders_background,
    remove_label_from_senders_background,
    archive_emails_background,
    mark_important_background,
    scan_unread_by_sender,
    mark_read_by_senders_background,
    mark_read_and_archive_by_senders_background,
    archive_unread_by_senders_background,
    delete_unread_by_senders_background,
)

router = APIRouter(prefix="/api", tags=["Actions"])
logger = logging.getLogger(__name__)


@router.post("/scan")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_scan(
    request: Request, body: ScanRequest, background_tasks: BackgroundTasks
):
    """Start email scan for unsubscribe links."""
    filters_dict = (
        body.filters.model_dump(exclude_none=True) if body.filters else None
    )
    background_tasks.add_task(scan_emails, body.limit, filters_dict)
    return {"status": "started"}


@router.post("/sign-in")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_sign_in(request: Request, background_tasks: BackgroundTasks):
    """Trigger OAuth sign-in flow."""
    background_tasks.add_task(get_gmail_service)
    return {"status": "signing_in"}


@router.post("/sign-out")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_sign_out(request: Request):
    """Sign out and clear credentials."""
    try:
        return sign_out()
    except Exception as e:
        logger.exception("Error during sign-out")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sign out",
        ) from e


@router.post("/unsubscribe")
@limiter.limit(ACTION_RATE_LIMIT)
async def api_unsubscribe(request: Request, body: UnsubscribeRequest):
    """Unsubscribe from a single sender."""
    try:
        return unsubscribe_single(body.domain, body.link)
    except Exception as e:
        logger.exception("Error during unsubscribe")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unsubscribe",
        ) from e


@router.post("/mark-read")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_mark_read(
    request: Request, body: MarkReadRequest, background_tasks: BackgroundTasks
):
    """Mark emails as read."""
    filters_dict = (
        body.filters.model_dump(exclude_none=True) if body.filters else None
    )
    background_tasks.add_task(mark_emails_as_read, body.count, filters_dict)
    return {"status": "started"}


@router.post("/delete-scan")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_delete_scan(
    request: Request,
    body: DeleteScanRequest,
    background_tasks: BackgroundTasks,
):
    """Scan senders for bulk delete."""
    filters_dict = (
        body.filters.model_dump(exclude_none=True) if body.filters else None
    )
    background_tasks.add_task(scan_senders_for_delete, body.limit, filters_dict)
    return {"status": "started"}


@router.post("/delete-emails")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_delete_emails(request: Request, body: DeleteEmailsRequest):
    """Delete emails from a specific sender."""
    if not body.sender or not body.sender.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sender email is required",
        )
    try:
        return delete_emails_by_sender(body.sender)
    except Exception as e:
        logger.exception("Error deleting emails")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete emails",
        ) from e


@router.post("/delete-emails-bulk")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_delete_emails_bulk(
    request: Request, body: DeleteBulkRequest, background_tasks: BackgroundTasks
):
    """Delete emails from multiple senders (background task with progress)."""
    background_tasks.add_task(delete_emails_bulk_background, body.senders)
    return {"status": "started"}


@router.post("/download-emails")
@limiter.limit(ACTION_RATE_LIMIT)
async def api_download_emails(
    request: Request,
    body: DownloadEmailsRequest,
    background_tasks: BackgroundTasks,
):
    """Start downloading email metadata for selected senders."""
    # Note: Empty list is allowed - service function will handle it gracefully
    background_tasks.add_task(download_emails_background, body.senders)
    return {"status": "started"}


# ----- Label Management Endpoints -----


@router.post("/labels")
@limiter.limit(ACTION_RATE_LIMIT)
async def api_create_label(request: Request, body: CreateLabelRequest):
    """Create a new Gmail label."""
    try:
        return create_label(body.name)
    except Exception as e:
        logger.exception("Error creating label")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create label",
        ) from e


@router.delete("/labels/{label_id}")
@limiter.limit(ACTION_RATE_LIMIT)
async def api_delete_label(request: Request, label_id: str):
    """Delete a Gmail label."""
    if not label_id or not label_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label ID is required",
        )
    try:
        return delete_label(label_id)
    except Exception as e:
        logger.exception("Error deleting label")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete label",
        ) from e


@router.post("/apply-label")
@limiter.limit(ACTION_RATE_LIMIT)
async def api_apply_label(
    request: Request, body: ApplyLabelRequest, background_tasks: BackgroundTasks
):
    """Apply a label to emails from selected senders."""
    if not body.label_id or not body.label_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label ID is required",
        )
    if not body.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(
        apply_label_to_senders_background, body.label_id, body.senders
    )
    return {"status": "started"}


@router.post("/remove-label")
@limiter.limit(ACTION_RATE_LIMIT)
async def api_remove_label(
    request: Request,
    body: RemoveLabelRequest,
    background_tasks: BackgroundTasks,
):
    """Remove a label from emails from selected senders."""
    if not body.label_id or not body.label_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label ID is required",
        )
    if not body.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(
        remove_label_from_senders_background, body.label_id, body.senders
    )
    return {"status": "started"}


@router.post("/archive")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_archive(
    request: Request, body: ArchiveRequest, background_tasks: BackgroundTasks
):
    """Archive emails from selected senders (remove from inbox)."""
    if not body.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(archive_emails_background, body.senders)
    return {"status": "started"}


@router.post("/mark-important")
@limiter.limit(ACTION_RATE_LIMIT)
async def api_mark_important(
    request: Request,
    body: MarkImportantRequest,
    background_tasks: BackgroundTasks,
):
    """Mark/unmark emails from selected senders as important."""
    if not body.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(
        partial(mark_important_background, body.senders, important=body.important)
    )
    return {"status": "started"}


# ----- Unread Email Endpoints -----


@router.post("/unread-scan")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_unread_scan(
    request: Request, body: UnreadScanRequest, background_tasks: BackgroundTasks
):
    """Scan unread emails grouped by sender."""
    filters_dict = (
        body.filters.model_dump(exclude_none=True) if body.filters else None
    )
    background_tasks.add_task(
        scan_unread_by_sender, body.limit, filters_dict, body.inbox_only
    )
    return {"status": "started"}


@router.post("/unread-mark-read")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_unread_mark_read(
    request: Request, body: UnreadActionRequest, background_tasks: BackgroundTasks
):
    """Mark unread emails from selected senders as read."""
    if not body.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(mark_read_by_senders_background, body.senders)
    return {"status": "started"}


@router.post("/unread-mark-read-archive")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_unread_mark_read_archive(
    request: Request, body: UnreadActionRequest, background_tasks: BackgroundTasks
):
    """Mark as read and archive unread emails from selected senders."""
    if not body.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(mark_read_and_archive_by_senders_background, body.senders)
    return {"status": "started"}


@router.post("/unread-archive")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_unread_archive(
    request: Request, body: UnreadActionRequest, background_tasks: BackgroundTasks
):
    """Archive unread emails (keep unread status)."""
    if not body.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(archive_unread_by_senders_background, body.senders)
    return {"status": "started"}


@router.post("/unread-delete")
@limiter.limit(HEAVY_OPERATION_RATE_LIMIT)
async def api_unread_delete(
    request: Request, body: UnreadActionRequest, background_tasks: BackgroundTasks
):
    """Delete unread emails (move to trash)."""
    if not body.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(delete_unread_by_senders_background, body.senders)
    return {"status": "started"}
