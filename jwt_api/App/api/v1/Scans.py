# App/api/v1/Scans.py
"""
Scan History API Endpoints (Verification Log & Ingestion Engine).

Permissions & Authorization Rules:
    - Normal User (Default with NO permissions):
        * Can freely view their OWN scan history (self-service).
        * Can view details and metrics for their own shifts.
        * Can log/sync scans to shifts they own.
    - Normal User with SCANS_VIEW_ANY:
        * Can view scan records and metrics across all users/shifts.
    - Normal User with SCANS_UPDATE:
        * Can update or annotate their own scan records.
    - Normal User with SCANS_DELETE:
        * Can delete their own scan records.
    - Admin (role == "admin"):
        * Can literally do anything: view all, search JSONB claims, update, delete, sync for any shift.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List

from App.core.Connector import get_db
from App.core.LoggingInit import get_core_logger
from App.core.exceptions import (
    ScanNotFoundError,
    ShiftNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from App.models.Permissions import Permission
from App.api.dependencies.auth import get_current_user
from App.api.dependencies.permissions import require_permission
from App.services.scan_history_service import ScanHistoryService
from App.schemas.ScanHistorySchema import (
    RecordScanRequest,
    BulkSyncScansRequest,
    UpdateScanRequest,
    ScanResponse,
    ScanListResponse,
    ShiftMetricsResponse,
    BulkSyncResponse,
)

logger = get_core_logger(__name__)
scans_router = APIRouter(prefix="/scans", tags=["Scan History"])


# ============================================================================
# READ ENDPOINTS (SELF-SERVICE FOR NORMAL USERS + ADMIN FULL ACCESS)
# ============================================================================
@scans_router.get(
    "/",
    response_model=ScanListResponse,
    summary="List scan history",
    description=(
        "Retrieve scan history. "
        "Rule 1: Normal users with NO permissions can view their OWN scan history. "
        "Rule 2: Admins or users with SCANS_VIEW_ANY can view scans across all users/shifts."
    ),
)
async def list_scans(
    shift_id: Optional[str] = Query(None, description="Filter by Shift UUID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status ('valid', 'invalid')"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScanHistoryService(db)
    try:
        return await service.list_scans(
            current_user=current_user,
            shift_id=shift_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
    except ShiftNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@scans_router.get(
    "/shifts/{shift_id}/metrics",
    response_model=ShiftMetricsResponse,
    summary="Get shift scan metrics",
    description="Retrieve aggregated valid vs invalid metrics for a shift.",
)
async def get_shift_metrics(
    shift_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScanHistoryService(db)
    try:
        return await service.get_shift_metrics(shift_id=shift_id, current_user=current_user)
    except ShiftNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@scans_router.get(
    "/{scan_id}",
    response_model=ScanResponse,
    summary="Get scan record by ID",
    description="Retrieve a specific scan. Normal users can view their own; admins any.",
)
async def get_scan_by_id(
    scan_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScanHistoryService(db)
    try:
        return await service.get_scan_by_id(scan_id=scan_id, current_user=current_user)
    except ScanNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@scans_router.post(
    "/search",
    response_model=List[ScanResponse],
    summary="Search scans by JSONB claim (Admin or SCANS_VIEW_ANY)",
    description="Inspect scans matching nested JWT claim key-values via PostgreSQL JSONB containment.",
)
async def search_by_claim(
    claim_key: str = Query(..., description="JWT claim key name"),
    expected_value: str = Query(..., description="Expected value to match"),
    shift_id: Optional[str] = Query(None, description="Optional shift scope"),
    limit: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.SCANS_VIEW_ANY], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = ScanHistoryService(db)
    return await service.search_by_claim(
        claim_key=claim_key,
        expected_value=expected_value,
        current_user=current_user,
        shift_id=shift_id,
        limit=limit,
    )


# ============================================================================
# WRITE & INGESTION ENDPOINTS (CLIENT/SCANNER SYNC)
# ============================================================================
@scans_router.post(
    "/",
    response_model=ScanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a single scan event",
    description="Appends a single verified scan to an active shift.",
)
async def record_scan(
    payload: RecordScanRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScanHistoryService(db)
    try:
        return await service.record_scan(
            shift_id=payload.shift_id,
            jwt_scanned=payload.jwt_scanned,
            status=payload.status,
            scanned_at=payload.scanned_at,
            reason=payload.reason,
            current_user=current_user,
        )
    except ShiftNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@scans_router.post(
    "/shifts/{shift_id}/sync",
    response_model=BulkSyncResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch sync scans from mobile device",
    description="High-throughput batch ingest endpoint. Appends up to 1000 scans in a single transaction round-trip.",
)
async def sync_scans(
    shift_id: str,
    payload: BulkSyncScansRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScanHistoryService(db)
    scans_raw = [s.model_dump() for s in payload.scans]

    try:
        return await service.bulk_sync_scans(
            shift_id=shift_id,
            scans_data=scans_raw,
            current_user=current_user,
        )
    except ShiftNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# UPDATE & DELETE ENDPOINTS (PERMISSIONS-GATED)
# ============================================================================
@scans_router.patch(
    "/{scan_id}",
    response_model=ScanResponse,
    summary="Update or annotate a scan record",
    description="Annotate or correct a scan status. Normal users require SCANS_UPDATE and must own the shift. Admins can update any scan.",
)
async def update_scan(
    scan_id: int,
    payload: UpdateScanRequest,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.SCANS_UPDATE], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = ScanHistoryService(db)
    try:
        return await service.update_scan(
            scan_id=scan_id,
            current_user=current_user,
            status=payload.status,
            reason=payload.reason,
        )
    except ScanNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@scans_router.delete(
    "/{scan_id}",
    summary="Delete a scan record",
    description="Permanently delete a scan log. Normal users require SCANS_DELETE and must own the shift. Admins can delete any scan.",
)
async def delete_scan(
    scan_id: int,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.SCANS_DELETE], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = ScanHistoryService(db)
    try:
        await service.delete_scan(scan_id=scan_id, current_user=current_user)
        return {"status": "success", "message": f"Scan record {scan_id} deleted successfully"}
    except ScanNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
