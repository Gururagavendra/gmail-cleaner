"""
Actions API Routes
------------------
POST endpoints for triggering operations.
"""

import logging
from functools import partial
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.api.deps import SessionContext, get_session_context
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
)

router = APIRouter(prefix="/api", tags=["Actions"])
logger = logging.getLogger(__name__)


@router.post("/scan")
async def api_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Start email scan for unsubscribe links."""
    filters_dict = (
        request.filters.model_dump(exclude_none=True) if request.filters else None
    )
    background_tasks.add_task(scan_emails, ctx.session, request.limit, filters_dict)
    return {"status": "started"}


def _get_request_host_and_scheme(request: Request) -> tuple[str, str]:
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto")
    host = forwarded_host or request.url.hostname or "localhost"
    if host and ":" in host and not host.startswith("["):
        host = host.split(":", 1)[0]
    scheme = (forwarded_proto or request.url.scheme or "http").split(",")[0].strip()
    if scheme not in ("http", "https"):
        scheme = "http"
    return host, scheme


@router.post("/sign-in")
async def api_sign_in(
    request: Request,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Trigger OAuth sign-in flow."""
    host, scheme = _get_request_host_and_scheme(request)
    ctx.session.oauth_host = host
    ctx.session.oauth_scheme = scheme
    background_tasks.add_task(get_gmail_service, ctx.session, ctx.token_json, host, scheme)
    return {"status": "signing_in"}


@router.post("/sign-out")
async def api_sign_out(ctx: SessionContext = Depends(get_session_context)):
    """Sign out and clear credentials."""
    try:
        return sign_out(ctx.session)
    except Exception as e:
        logger.exception("Error during sign-out")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sign out",
        ) from e


@router.post("/unsubscribe")
async def api_unsubscribe(request: UnsubscribeRequest):
    """Unsubscribe from a single sender."""
    try:
        return unsubscribe_single(request.domain, request.link)
    except Exception as e:
        logger.exception("Error during unsubscribe")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unsubscribe",
        ) from e


@router.post("/mark-read")
async def api_mark_read(
    request: MarkReadRequest,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Mark emails as read."""
    filters_dict = (
        request.filters.model_dump(exclude_none=True) if request.filters else None
    )
    background_tasks.add_task(
        mark_emails_as_read, ctx.session, request.count, filters_dict
    )
    return {"status": "started"}


@router.post("/delete-scan")
async def api_delete_scan(
    request: DeleteScanRequest,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Scan senders for bulk delete."""
    filters_dict = (
        request.filters.model_dump(exclude_none=True) if request.filters else None
    )
    background_tasks.add_task(
        scan_senders_for_delete, ctx.session, request.limit, filters_dict
    )
    return {"status": "started"}


@router.post("/delete-emails")
async def api_delete_emails(
    request: DeleteEmailsRequest,
    ctx: SessionContext = Depends(get_session_context),
):
    """Delete emails from a specific sender."""
    if not request.sender or not request.sender.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sender email is required",
        )
    try:
        return delete_emails_by_sender(ctx.session, request.sender)
    except Exception as e:
        logger.exception("Error deleting emails")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete emails",
        ) from e


@router.post("/delete-emails-bulk")
async def api_delete_emails_bulk(
    request: DeleteBulkRequest,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Delete emails from multiple senders (background task with progress)."""
    background_tasks.add_task(
        delete_emails_bulk_background, ctx.session, request.senders
    )
    return {"status": "started"}


@router.post("/download-emails")
async def api_download_emails(
    request: DownloadEmailsRequest,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Start downloading email metadata for selected senders."""
    # Note: Empty list is allowed - service function will handle it gracefully
    background_tasks.add_task(download_emails_background, ctx.session, request.senders)
    return {"status": "started"}


# ----- Label Management Endpoints -----


@router.post("/labels")
async def api_create_label(
    request: CreateLabelRequest,
    ctx: SessionContext = Depends(get_session_context),
):
    """Create a new Gmail label."""
    try:
        return create_label(ctx.session, request.name)
    except Exception as e:
        logger.exception("Error creating label")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create label",
        ) from e


@router.delete("/labels/{label_id}")
async def api_delete_label(
    label_id: str, ctx: SessionContext = Depends(get_session_context)
):
    """Delete a Gmail label."""
    if not label_id or not label_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label ID is required",
        )
    try:
        return delete_label(ctx.session, label_id)
    except Exception as e:
        logger.exception("Error deleting label")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete label",
        ) from e


@router.post("/apply-label")
async def api_apply_label(
    request: ApplyLabelRequest,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Apply a label to emails from selected senders."""
    if not request.label_id or not request.label_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label ID is required",
        )
    if not request.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(
        apply_label_to_senders_background,
        ctx.session,
        request.label_id,
        request.senders,
    )
    return {"status": "started"}


@router.post("/remove-label")
async def api_remove_label(
    request: RemoveLabelRequest,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Remove a label from emails from selected senders."""
    if not request.label_id or not request.label_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label ID is required",
        )
    if not request.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(
        remove_label_from_senders_background,
        ctx.session,
        request.label_id,
        request.senders,
    )
    return {"status": "started"}


@router.post("/archive")
async def api_archive(
    request: ArchiveRequest,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Archive emails from selected senders (remove from inbox)."""
    if not request.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(archive_emails_background, ctx.session, request.senders)
    return {"status": "started"}


@router.post("/mark-important")
async def api_mark_important(
    request: MarkImportantRequest,
    background_tasks: BackgroundTasks,
    ctx: SessionContext = Depends(get_session_context),
):
    """Mark/unmark emails from selected senders as important."""
    if not request.senders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one sender is required",
        )
    background_tasks.add_task(
        partial(
            mark_important_background,
            ctx.session,
            request.senders,
            important=request.important,
        )
    )
    return {"status": "started"}
