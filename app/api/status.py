"""
Status API Routes
-----------------
GET endpoints for checking status of various operations.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.services import (
    get_scan_status,
    get_scan_results,
    check_login_status,
    get_web_auth_status,
    get_unread_count,
    get_mark_read_status,
    get_delete_scan_status,
    get_delete_scan_results,
    get_delete_bulk_status,
    get_download_status,
    get_download_csv,
    get_labels,
    get_label_operation_status,
    get_archive_status,
    get_important_status,
)

router = APIRouter(prefix="/api", tags=["Status"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def api_status():
    """Get email scan status."""
    try:
        return get_scan_status()
    except Exception as e:
        logger.exception("Error getting scan status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get scan status",
        ) from e


@router.get("/results")
async def api_results():
    """Get email scan results."""
    try:
        return get_scan_results()
    except Exception as e:
        logger.exception("Error getting scan results")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get scan results",
        ) from e


@router.get("/auth-status")
async def api_auth_status():
    """Get authentication status."""
    try:
        return check_login_status()
    except Exception as e:
        logger.exception("Error getting auth status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get auth status",
        ) from e


@router.get("/web-auth-status")
async def api_web_auth_status():
    """Get web auth status for Docker/headless mode."""
    try:
        return get_web_auth_status()
    except Exception as e:
        logger.exception("Error getting web auth status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get web auth status",
        ) from e


@router.get("/unread-count")
async def api_unread_count():
    """Get unread email count."""
    try:
        return get_unread_count()
    except Exception as e:
        logger.exception("Error getting unread count")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unread count",
        ) from e


@router.get("/mark-read-status")
async def api_mark_read_status():
    """Get mark-as-read operation status."""
    try:
        return get_mark_read_status()
    except Exception as e:
        logger.exception("Error getting mark-read status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get mark-read status",
        ) from e


@router.get("/delete-scan-status")
async def api_delete_scan_status():
    """Get delete scan status."""
    try:
        return get_delete_scan_status()
    except Exception as e:
        logger.exception("Error getting delete scan status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get delete scan status",
        ) from e


@router.get("/delete-scan-results")
async def api_delete_scan_results():
    """Get delete scan results (senders grouped by count)."""
    try:
        return get_delete_scan_results()
    except Exception as e:
        logger.exception("Error getting delete scan results")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get delete scan results",
        ) from e


@router.get("/download-status")
async def api_download_status():
    """Get download operation status."""
    try:
        return get_download_status()
    except Exception as e:
        logger.exception("Error getting download status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get download status",
        ) from e


@router.get("/download-csv")
async def api_download_csv():
    """Get the generated CSV file."""
    try:
        csv_data = get_download_csv()
        if not csv_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No CSV data available",
            )

        filename = f"emails-backup-{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')}.csv"

        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting CSV download")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get CSV download",
        ) from e


@router.get("/delete-bulk-status")
async def api_delete_bulk_status():
    """Get bulk delete operation status."""
    try:
        return get_delete_bulk_status()
    except Exception as e:
        logger.exception("Error getting delete bulk status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get delete bulk status",
        ) from e


# ----- Label Management Endpoints -----


@router.get("/labels")
async def api_get_labels():
    """Get all Gmail labels."""
    try:
        return get_labels()
    except Exception as e:
        logger.exception("Error getting labels")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get labels",
        ) from e


@router.get("/label-operation-status")
async def api_label_operation_status():
    """Get label operation status (apply/remove)."""
    try:
        return get_label_operation_status()
    except Exception as e:
        logger.exception("Error getting label operation status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get label operation status",
        ) from e


@router.get("/archive-status")
async def api_archive_status():
    """Get archive operation status."""
    try:
        return get_archive_status()
    except Exception as e:
        logger.exception("Error getting archive status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get archive status",
        ) from e


@router.get("/important-status")
async def api_important_status():
    """Get mark important operation status."""
    try:
        return get_important_status()
    except Exception as e:
        logger.exception("Error getting important status")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get important status",
        ) from e
