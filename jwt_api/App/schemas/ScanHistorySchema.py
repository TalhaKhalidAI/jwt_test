# App/schemas/ScanHistorySchema.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class RecordScanRequest(BaseModel):
    """Payload to record a single scan event."""
    shift_id: str = Field(..., description="Active Shift UUID")
    jwt_scanned: Dict[str, Any] = Field(..., description="Decoded JWT claims payload from scanned item")
    status: str = Field(..., max_length=10, description="Verification status (e.g. 'valid', 'invalid')")
    scanned_at: datetime = Field(..., description="Timestamp when scan was captured by the client device")
    reason: Optional[str] = Field(None, max_length=255, description="Optional failure reason or annotation")


class ScanItemSync(BaseModel):
    """Single scan payload within an offline batch sync."""
    jwt_scanned: Dict[str, Any] = Field(..., description="Decoded JWT claims payload")
    status: str = Field(..., max_length=10, description="Status code ('valid', 'invalid')")
    scanned_at: datetime = Field(..., description="Local device scan timestamp")
    reason: Optional[str] = Field(None, max_length=255)


class BulkSyncScansRequest(BaseModel):
    """Batch payload sent by mobile scanner on reconnect."""
    scans: List[ScanItemSync] = Field(..., min_length=1, max_length=1000, description="Batch of collected scans")


class UpdateScanRequest(BaseModel):
    """Payload to annotate or correct a scan status (requires SCANS_UPDATE or Admin)."""
    status: Optional[str] = Field(None, max_length=10)
    reason: Optional[str] = Field(None, max_length=255)


class ScanResponse(BaseModel):
    """Public representation of an ingested scan record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    shift_id: str
    jwt_scanned: Dict[str, Any]
    status: str
    reason: Optional[str] = None
    scanned_at: Optional[str] = None
    synced_at: Optional[str] = None


class ScanListResponse(BaseModel):
    """Paginated collection of scan records."""
    items: List[ScanResponse]
    limit: int
    offset: int
    total: int


class ShiftMetricsResponse(BaseModel):
    """Shift scan summary statistics."""
    shift_id: str
    total_scans: int
    breakdown: Dict[str, int]


class BulkSyncResponse(BaseModel):
    """Response returned upon batch sync completion."""
    shift_id: str
    synced_count: int
    synced_at: str
