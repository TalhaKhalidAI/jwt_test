# App/repository/ShiftRepository.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, List
import logging
from datetime import datetime, timezone
import uuid

# Import your Shift model (adjust path if needed based on your file structure)
from App.api.databases.MigrateTable import Shift as ShiftModel
from App.core.exceptions import (
    ShiftNotFoundError,
    ActiveShiftExistsError,
    InvalidShiftStateError,
    InfrastructureError
)
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class ShiftRepository:
    """
    Repository for Shift (Session Management) operations.

    Transaction policy:
        This repository does NOT commit. The service layer owns
        transaction boundaries (Database.session() commits at the end
        of the request).

    Error-handling convention:
        - Lookup methods (get_by_*) propagate DB errors untouched.
        - Write methods raise domain errors for expected business
          conditions (ShiftNotFoundError, InvalidShiftStateError, etc.).
        - Foreign key violations (e.g., invalid user_id or key_id) are 
          translated to InfrastructureError or DomainError.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ================================================================
    # INTERNAL HELPERS
    # ================================================================
    async def _safe_flush(self) -> None:
        """Flush pending ORM changes. Lets IntegrityError propagate so the
        caller can translate a specific constraint violation."""
        await self.session.flush()

    # ================================================================
    # BASIC CRUD
    # ================================================================
    async def get_by_id(self, shift_id: str | uuid.UUID) -> Optional[ShiftModel]:
        result = await self.session.execute(
            select(ShiftModel).where(ShiftModel.id == shift_id)
        )
        return result.scalar_one_or_none()

    async def get_active_shift_by_user(self, user_id: int) -> Optional[ShiftModel]:
        """Check if a user already has an active shift (prevents double login)."""
        result = await self.session.execute(
            select(ShiftModel)
            .where(ShiftModel.user_id == user_id)
            .where(ShiftModel.status == "active")
            .order_by(ShiftModel.started_at.desc())
        )
        return result.scalars().first()

    async def get_active_shifts(self) -> List[ShiftModel]:
        """Get all currently active shifts (for the Admin dashboard)."""
        result = await self.session.execute(
            select(ShiftModel)
            .where(ShiftModel.status == "active")
            .order_by(ShiftModel.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_shifts_by_user(self, user_id: int, limit: int = 50) -> List[ShiftModel]:
        """Get shift history for a specific user."""
        result = await self.session.execute(
            select(ShiftModel)
            .where(ShiftModel.user_id == user_id)
            .order_by(ShiftModel.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ================================================================
    # LIFECYCLE METHODS
    # ================================================================
    async def create_shift(
        self,
        user_id: int,
        key_id: str | uuid.UUID,
        expires_at: datetime,
        device_id: Optional[str] = None,
    ) -> ShiftModel:
        """Create a new active shift. Does NOT commit.
        
        Raises:
            ActiveShiftExistsError: If the user already has an active shift.
            InfrastructureError: If user_id or key_id violates foreign keys.
        """
        # 1. Ensure the user doesn't already have an active shift
        existing = await self.get_active_shift_by_user(user_id)
        if existing:
            raise ActiveShiftExistsError(
                f"User {user_id} already has an active shift ({existing.id})"
            )

        # 2. Create the Shift
        shift = ShiftModel(
            user_id=user_id,
            key_id=key_id,
            expires_at=expires_at,
            device_id=device_id,
            status="active"
        )
        self.session.add(shift)

        try:
            await self._safe_flush()
        except IntegrityError as e:
            msg = str(e.orig).lower()
            if "foreign key constraint" in msg:
                raise InfrastructureError(
                    f"Invalid user_id ({user_id}) or key_id ({key_id}) - foreign key violation"
                ) from e
            raise  # Let other DB errors propagate to global handler

        await self.session.refresh(shift)
        logger.info(f"Created new shift: {shift.id} for user {user_id}")
        return shift

    async def complete_shift(self, shift_id: str | uuid.UUID) -> ShiftModel:
        """Mark a shift as completed (Checkout). Does NOT commit.
        
        Raises:
            ShiftNotFoundError: If shift doesn't exist.
            InvalidShiftStateError: If shift is not 'active'.
        """
        shift = await self.get_by_id(shift_id)
        if not shift:
            raise ShiftNotFoundError(f"Shift {shift_id} not found")

        if shift.status != "active":
            raise InvalidShiftStateError(
                f"Cannot complete shift {shift_id}: current status is '{shift.status}'"
            )

        shift.status = "completed"
        shift.ended_at = datetime.now(timezone.utc)
        
        await self._safe_flush()
        await self.session.refresh(shift)
        logger.info(f"Completed shift: {shift.id}")
        return shift

    async def revoke_shift(
        self, 
        shift_id: str | uuid.UUID, 
        reason: str = "Revoked by admin"
    ) -> ShiftModel:
        """Forcefully revoke an active shift. Does NOT commit.
        
        Raises:
            ShiftNotFoundError: If shift doesn't exist.
            InvalidShiftStateError: If shift is not 'active'.
        """
        shift = await self.get_by_id(shift_id)
        if not shift:
            raise ShiftNotFoundError(f"Shift {shift_id} not found")

        if shift.status != "active":
            raise InvalidShiftStateError(
                f"Cannot revoke shift {shift_id}: current status is '{shift.status}'"
            )

        shift.status = "revoked"
        shift.revoked_reason = reason
        shift.ended_at = datetime.now(timezone.utc)

        await self._safe_flush()
        await self.session.refresh(shift)
        logger.warning(f"Revoked shift: {shift.id} - Reason: {reason}")
        return shift

    async def expire_old_shifts(self) -> int:
        """Bulk expire shifts where expires_at < NOW() and status is 'active'.
        
        Useful for a background cron job / scheduled task.
        Returns the number of shifts expired.
        """
        now = datetime.now(timezone.utc)
        
        # We use an UPDATE statement for efficiency
        stmt = (
            update(ShiftModel)
            .where(ShiftModel.status == "active")
            .where(ShiftModel.expires_at < now)
            .values(
                status="expired", 
                ended_at=now
            )
            .returning(ShiftModel.id)
        )
        
        result = await self.session.execute(stmt)
        expired_ids = result.scalars().all()
        
        if expired_ids:
            logger.info(f"Expired {len(expired_ids)} old shifts")
            
        return len(expired_ids)