"""
Actions API Routes
------------------
POST endpoints for triggering operations.
"""

from fastapi import APIRouter, BackgroundTasks

from app.models import (
    ScanRequest,
    MarkReadRequest,
    DeleteScanRequest,
    UnsubscribeRequest,
    DeleteEmailsRequest,
    DeleteBulkRequest,
)
from app.services import (
    scan_emails,
    get_gmail_service,
    sign_out,
    unsubscribe_single,
    mark_emails_as_read,
    scan_senders_for_delete,
    delete_emails_by_sender,
    delete_emails_bulk,
    delete_emails_bulk_background,
)

router = APIRouter(prefix="/api", tags=["Actions"])


@router.post("/scan")
async def api_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Start email scan for unsubscribe links."""
    background_tasks.add_task(scan_emails, request.limit, request.filters)
    return {"status": "started"}


@router.post("/sign-in")
async def api_sign_in(background_tasks: BackgroundTasks):
    """Trigger OAuth sign-in flow."""
    background_tasks.add_task(get_gmail_service)
    return {"status": "signing_in"}


@router.post("/sign-out")
async def api_sign_out():
    """Sign out and clear credentials."""
    return sign_out()


@router.post("/unsubscribe")
async def api_unsubscribe(request: UnsubscribeRequest):
    """Unsubscribe from a single sender."""
    return unsubscribe_single(request.domain, request.link)


@router.post("/mark-read")
async def api_mark_read(request: MarkReadRequest, background_tasks: BackgroundTasks):
    """Mark emails as read."""
    background_tasks.add_task(mark_emails_as_read, request.count, request.filters)
    return {"status": "started"}


@router.post("/delete-scan")
async def api_delete_scan(request: DeleteScanRequest, background_tasks: BackgroundTasks):
    """Scan senders for bulk delete."""
    background_tasks.add_task(scan_senders_for_delete, request.limit, request.filters)
    return {"status": "started"}


@router.post("/delete-emails")
async def api_delete_emails(request: DeleteEmailsRequest):
    """Delete emails from a specific sender."""
    return delete_emails_by_sender(request.sender)


@router.post("/delete-emails-bulk")
async def api_delete_emails_bulk(request: DeleteBulkRequest, background_tasks: BackgroundTasks):
    """Delete emails from multiple senders (background task with progress)."""
    background_tasks.add_task(delete_emails_bulk_background, request.senders)
    return {"status": "started"}
