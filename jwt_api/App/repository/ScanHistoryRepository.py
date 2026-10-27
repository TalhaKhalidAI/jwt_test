# App/repository/ScanHistoryRepository.py

from datetime import datetime, timezone
import logging
from typing import Optional, List, Dict, Any
import uuid

from sqlalchemy import select, desc, func, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from App.api.databases.MigrateTable import ScanHistory as ScanHistoryModel
from App.core.exceptions import (
    ScanNotFoundError,
    ShiftNotFoundError,
    InfrastructureError,
)

logger = logging.getLogger(__name__)


class ScanHistoryRepository:
    """
    Repository for ScanHistory (High-throughput verification log) operations.

    Transaction policy:
        This repository does NOT commit. The service layer manages transactions
        (e.g., batch sync endpoints commit once per batch request).

    Architectural design:
        - Write-heavy append-only log model.
        - Provides both single insert and high-throughput batch insert (bulk_create).
        - Rich JSONB querying capabilities for JWT claims inspection.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ================================================================
    # INTERNAL HELPERS
    # ================================================================
    @staticmethod
    def _parse_uuid(val: str | uuid.UUID) -> Optional[uuid.UUID]:
        """Safely parse string or UUID object to prevent asyncpg type errors."""
        if isinstance(val, uuid.UUID):
            return val
        try:
            return uuid.UUID(str(val))
        except (ValueError, AttributeError):
            return None

    async def _safe_flush(self) -> None:
        """Flush pending ORM operations without committing."""
        await self.session.flush()

    # ================================================================
    # READ OPERATIONS
    # ================================================================
    async def get_by_id(self, scan_id: int) -> Optional[ScanHistoryModel]:
        """Retrieve a specific scan by its BigInteger primary key."""
        result = await self.session.execute(
            select(ScanHistoryModel).where(ScanHistoryModel.id == scan_id)
        )
        return result.scalar_one_or_none()

    async def get_by_shift(
        self,
        shift_id: str | uuid.UUID,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ScanHistoryModel]:
        """
        Fetch paginated scans associated with a specific shift,
        ordered chronologically by scan time (most recent first).
        """
        parsed_shift_id = self._parse_uuid(shift_id)
        if not parsed_shift_id:
            return []

        stmt = (
            select(ScanHistoryModel)
            .where(ScanHistoryModel.shift_id == parsed_shift_id)
            .order_by(desc(ScanHistoryModel.scanned_at))
        )
        if status:
            stmt = stmt.where(ScanHistoryModel.status == status)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_shift_metrics(self, shift_id: str | uuid.UUID) -> Dict[str, Any]:
        """
        Aggregate scan statistics for a shift (Total, Valid, Invalid, etc.).
        Essential for worker shift checkout and real-time supervisor auditing.
        """
        parsed_shift_id = self._parse_uuid(shift_id)
        if not parsed_shift_id:
            return {"total": 0, "breakdown": {}}

        stmt = (
            select(
                ScanHistoryModel.status,
                func.count(ScanHistoryModel.id).label("count")
            )
            .where(ScanHistoryModel.shift_id == parsed_shift_id)
            .group_by(ScanHistoryModel.status)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        breakdown = {row[0]: row[1] for row in rows}
        total = sum(breakdown.values())

        return {
            "shift_id": str(parsed_shift_id),
            "total_scans": total,
            "breakdown": breakdown,
        }

    async def search_by_jwt_claim(
        self,
        claim_key: str,
        expected_value: Any,
        shift_id: Optional[str | uuid.UUID] = None,
        limit: int = 50,
    ) -> List[ScanHistoryModel]:
        """
        Query scans matching a specific key-value claim inside the JSONB payload.
        Example: finding scans for a specific serial_number, lot_id, or product_id.
        """
        # PostgreSQL JSONB containment operator (@>)
        filter_json = {claim_key: expected_value}
        stmt = (
            select(ScanHistoryModel)
            .where(ScanHistoryModel.jwt_scanned.contains(filter_json))
            .order_by(desc(ScanHistoryModel.scanned_at))
            .limit(limit)
        )

        if shift_id:
            parsed_shift_id = self._parse_uuid(shift_id)
            if parsed_shift_id:
                stmt = stmt.where(ScanHistoryModel.shift_id == parsed_shift_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_scans(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[ScanHistoryModel]:
        """Real-time monitoring feed for ops dashboards."""
        stmt = select(ScanHistoryModel).order_by(desc(ScanHistoryModel.synced_at))
        if status:
            stmt = stmt.where(ScanHistoryModel.status == status)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ================================================================
    # WRITE OPERATIONS
    # ================================================================
    async def create(
        self,
        shift_id: str | uuid.UUID,
        jwt_scanned: Dict[str, Any],
        status: str,
        scanned_at: datetime,
        reason: Optional[str] = None,
    ) -> ScanHistoryModel:
        """
        Append a single scan record. Does NOT commit.

        Raises:
            ShiftNotFoundError: If the shift_id does not correspond to a valid shift.
        """
        parsed_shift_id = self._parse_uuid(shift_id)
        if not parsed_shift_id:
            raise ShiftNotFoundError(f"Invalid shift_id format: {shift_id}")

        scan = ScanHistoryModel(
            shift_id=parsed_shift_id,
            jwt_scanned=jwt_scanned,
            status=status,
            reason=reason,
            scanned_at=scanned_at,
        )
        self.session.add(scan)

        try:
            await self._safe_flush()
        except IntegrityError as e:
            msg = str(e.orig).lower() if hasattr(e, "orig") and e.orig else str(e).lower()
            if "foreign key" in msg and "shifts" in msg:
                raise ShiftNotFoundError(
                    f"Shift {shift_id} does not exist (foreign key constraint violated)"
                ) from e
            raise

        await self.session.refresh(scan)
        return scan

    async def bulk_create(
        self,
        scans: List[Dict[str, Any]],
    ) -> List[ScanHistoryModel]:
        """
        Batch append multiple scan records in a single database round-trip.
        Critical for offline sync from handheld scanners. Does NOT commit.

        Each dictionary must contain:
            - shift_id: str | uuid.UUID
            - jwt_scanned: dict
            - status: str
            - scanned_at: datetime
            - reason: Optional[str]
        """
        if not scans:
            return []

        scan_models = []
        for item in scans:
            parsed_shift_id = self._parse_uuid(item["shift_id"])
            if not parsed_shift_id:
                raise ShiftNotFoundError(f"Invalid shift_id: {item.get('shift_id')}")

            scan_models.append(
                ScanHistoryModel(
                    shift_id=parsed_shift_id,
                    jwt_scanned=item["jwt_scanned"],
                    status=item["status"],
                    reason=item.get("reason"),
                    scanned_at=item["scanned_at"],
                )
            )

        self.session.add_all(scan_models)

        try:
            await self._safe_flush()
        except IntegrityError as e:
            msg = str(e.orig).lower() if hasattr(e, "orig") and e.orig else str(e).lower()
            if "foreign key" in msg and "shifts" in msg:
                raise ShiftNotFoundError(
                    "One or more scans reference a non-existent shift_id"
                ) from e
            raise

        logger.info(f"Successfully bulk synced {len(scan_models)} scan records")
        return scan_models
