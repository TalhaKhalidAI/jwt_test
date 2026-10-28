# App/schemas/ShiftSchema.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List


class StartShiftRequest(BaseModel):
    """Payload to start a new work session / shift."""
    target_user_id: Optional[int] = Field(
        None, 
        description="Target user ID to start shift for (Admin-only capability. Normal users start shifts for themselves)"
    )
    key_id: Optional[str] = Field(
        None, 
        description="Optional CryptoKey UUID to bind to this shift (Defaults automatically to the primary active key)"
    )
    duration_hours: int = Field(8, ge=1, le=24, description="Shift duration in hours (1-24)")
    device_id: Optional[str] = Field(None, max_length=255, description="Physical scanner or handheld device serial/ID")


class RevokeShiftRequest(BaseModel):
    """Payload to forcefully revoke an active shift."""
    reason: str = Field(..., min_length=3, max_length=255, description="Administrative justification for revocation")


class ShiftResponse(BaseModel):
    """Public representation of a shift."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    key_id: str
    device_id: Optional[str] = None
    status: str
    started_at: Optional[str] = None
    expires_at: Optional[str] = None
    ended_at: Optional[str] = None
    revoked_reason: Optional[str] = None


class StartShiftResponse(BaseModel):
    """Response returned upon shift start, containing the scoped shift_token JWT."""
    shift: ShiftResponse
    shift_token: str
    expires_at: str


class ShiftListResponse(BaseModel):
    """Paginated collection of shifts."""
    items: List[ShiftResponse]
    limit: int
    offset: int
    total: int


class ExpireShiftsResponse(BaseModel):
    """Response returned by shift maintenance job."""
    expired_shifts_count: int
