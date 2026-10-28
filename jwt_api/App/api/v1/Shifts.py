# App/api/v1/Shifts.py
"""
Shift Management API Endpoints (Worker Floor Session & Scanner Authorization).

Permissions & Authorization Rules:
    - Normal User:
        * Can start a shift for THEMSELVES (receives scoped shift_token JWT).
        * Can checkout of their OWN active shift.
        * Can view their active shift and shift history.
        * CANNOT update, delete, or modify arbitrary shift records.
        * CANNOT start shifts for other users (403 Forbidden).
        * CANNOT revoke shifts (403 Forbidden).
    - Normal User with permissions:
        * SHIFTS_VIEW: Can view other users' shifts.
        * SHIFTS_REVOKE: Can administratively revoke active shifts.
    - Admin (role == "admin"):
        * Can do anything on ANY account (start, checkout, revoke, view, expire-old).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from App.core.Connector import get_db
from App.core.LoggingInit import get_core_logger
from App.core.exceptions import (
    ShiftNotFoundError,
    ActiveShiftExistsError,
    InvalidShiftStateError,
    CryptoKeyNotFoundError,
    UserNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from App.models.Permissions import Permission
from App.api.dependencies.auth import get_current_user
from App.api.dependencies.permissions import require_permission
from App.services.shift_service import ShiftService
from App.schemas.ShiftSchema import (
    StartShiftRequest,
    RevokeShiftRequest,
    ShiftResponse,
    StartShiftResponse,
    ShiftListResponse,
    ExpireShiftsResponse,
)

logger = get_core_logger(__name__)
shifts_router = APIRouter(prefix="/shifts", tags=["Shifts & Sessions"])


# ============================================================================
# READ ENDPOINTS
# ============================================================================
@shifts_router.get(
    "/active/me",
    response_model=Optional[ShiftResponse],
    summary="Get current user's active shift",
    description="Worker self-service endpoint to check if they currently have an open active shift.",
)
async def get_my_active_shift(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ShiftService(db)
    return await service.get_my_active_shift(current_user=current_user)


@shifts_router.get(
    "/",
    response_model=ShiftListResponse,
    summary="List shifts",
    description=(
        "Retrieve shifts. "
        "Normal users receive their OWN shift history. "
        "Admins or users with SHIFTS_VIEW can list all active shifts across the company or filter by user_id."
    ),
)
async def list_shifts(
    user_id: Optional[int] = Query(None, description="Filter by user ID (Admin/Supervisor only)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ShiftService(db)
    return await service.list_shifts(
        current_user=current_user,
        target_user_id=user_id,
        limit=limit,
        offset=offset,
    )


@shifts_router.get(
    "/{shift_id}",
    response_model=ShiftResponse,
    summary="Get shift by ID",
    description="Fetch a specific shift. Normal users can only view shifts they own; admins any.",
)
async def get_shift_by_id(
    shift_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ShiftService(db)
    try:
        return await service.get_shift_by_id(shift_id=shift_id, current_user=current_user)
    except ShiftNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# ============================================================================
# LIFECYCLE: START & CHECKOUT
# ============================================================================
@shifts_router.post(
    "/start",
    response_model=StartShiftResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new work shift",
    description=(
        "Initiates a work shift and returns a scoped shift_token JWT for mobile scanner authorization. "
        "Normal workers can start shifts for THEMSELVES. "
        "Admins can specify target_user_id to start a shift on behalf of any worker."
    ),
)
async def start_shift(
    payload: StartShiftRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ShiftService(db)
    try:
        return await service.start_shift(
            current_user=current_user,
            target_user_id=payload.target_user_id,
            key_id=payload.key_id,
            duration_hours=payload.duration_hours,
            device_id=payload.device_id,
        )
    except ActiveShiftExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@shifts_router.post(
    "/checkout",
    response_model=ShiftResponse,
    summary="Checkout of current active shift (Self-Service)",
    description="Worker self-service endpoint to complete their currently active shift at the end of the workday.",
)
async def checkout_my_shift(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ShiftService(db)
    active_shift = await service.get_my_active_shift(current_user=current_user)
    if not active_shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You do not have any currently active shift to checkout from",
        )

    try:
        return await service.checkout_shift(
            shift_id=active_shift["id"],
            current_user=current_user,
        )
    except InvalidShiftStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@shifts_router.post(
    "/{shift_id}/checkout",
    response_model=ShiftResponse,
    summary="Checkout of a specific shift",
    description="Complete a shift by ID. Workers can checkout their own shift; admins can checkout any worker's shift.",
)
async def checkout_shift_by_id(
    shift_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ShiftService(db)
    try:
        return await service.checkout_shift(
            shift_id=shift_id,
            current_user=current_user,
        )
    except ShiftNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InvalidShiftStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# ADMINISTRATIVE: REVOKE & EXPIRY MAINTENANCE
# ============================================================================
@shifts_router.post(
    "/{shift_id}/revoke",
    response_model=ShiftResponse,
    summary="Forcefully revoke an active shift (Admin / Supervisor)",
    description="Terminates an active shift and blacklists the shift_token in Redis. Requires SHIFTS_REVOKE or Admin.",
)
async def revoke_shift(
    shift_id: str,
    payload: RevokeShiftRequest,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.SHIFTS_REVOKE], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = ShiftService(db)
    try:
        return await service.revoke_shift(
            shift_id=shift_id,
            reason=payload.reason,
            current_user=current_user,
        )
    except ShiftNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InvalidShiftStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@shifts_router.post(
    "/expire-old",
    response_model=ExpireShiftsResponse,
    summary="Trigger bulk expiry of expired shifts (Admin Only)",
    description="Bulk expires active shifts past their expiration timestamp.",
)
async def expire_old_shifts(
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.ADMIN_ACCESS], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = ShiftService(db)
    return await service.expire_old_shifts(current_user=current_user)
