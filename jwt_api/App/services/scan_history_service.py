# App/services/scan_history_service.py

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from App.services.base import BaseService
from App.repository.ScanHistoryRepository import ScanHistoryRepository
from App.repository.ShiftRepository import ShiftRepository
from App.core.exceptions import (
    ScanNotFoundError,
    ShiftNotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from App.models.Permissions import Permission
from App.core.LoggingInit import get_core_logger

logger = get_core_logger(__name__)


class ScanHistoryService(BaseService):
    """
    Application business logic for ScanHistory (Verification Log) operations.

    Authorization Rules:
        - Admin (role == "admin"): Can do literally anything (view all, update, delete, search).
        - Normal User (default with no permissions): Can view their OWN scan history.
        - Normal User with SCANS_VIEW_ANY: Can view any scan history across any user/shift.
        - Normal User with SCANS_UPDATE: Can update/annotate their own scan records.
        - Normal User with SCANS_DELETE: Can delete their own scan records.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.db = db
        self.repo = ScanHistoryRepository(db)
        self.shift_repo = ShiftRepository(db)

    # ================================================================
    # INTERNAL HELPERS
    # ================================================================
    @staticmethod
    def _is_admin(current_user: Dict[str, Any]) -> bool:
        return current_user.get("role") == "admin"

    @staticmethod
    def _get_user_id(current_user: Dict[str, Any]) -> int:
        return current_user.get("user_id") or current_user.get("id")

    @staticmethod
    def _has_permission(current_user: Dict[str, Any], perm: Permission) -> bool:
        if current_user.get("role") == "admin":
            return True
        perms = current_user.get("permissions", {})
        return bool(perms.get(perm.value if isinstance(perm, Permission) else perm, False))

    async def _verify_scan_ownership(
        self, scan, current_user: Dict[str, Any], require_perm: Optional[Permission] = None
    ) -> None:
        """Verify that current_user has access to manage this scan record."""
        if self._is_admin(current_user):
            return

        if require_perm and not self._has_permission(current_user, require_perm):
            raise PermissionDeniedError(f"Missing required permission: {require_perm.value}")

        # Fetch shift to verify user ownership
        shift = await self.shift_repo.get_by_id(scan.shift_id)
        user_id = self._get_user_id(current_user)
        if not shift or shift.user_id != user_id:
            logger.warning(
                f"Unauthorized scan access: User {user_id} attempted to access scan {scan.id} belonging to user {getattr(shift, 'user_id', None)}"
            )
            raise PermissionDeniedError("You do not have permission to access or modify this scan record")

    @staticmethod
    def _to_dict(scan) -> Dict[str, Any]:
        return {
            "id": scan.id,
            "shift_id": str(scan.shift_id),
            "jwt_scanned": scan.jwt_scanned,
            "status": scan.status,
            "reason": scan.reason,
            "scanned_at": scan.scanned_at.isoformat() if scan.scanned_at else None,
            "synced_at": scan.synced_at.isoformat() if scan.synced_at else None,
        }

    # ================================================================
    # READ OPERATIONS
    # ================================================================
    async def get_scan_by_id(
        self, scan_id: int, current_user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fetch a specific scan by ID.
        - Admin or SCANS_VIEW_ANY: Can view any scan.
        - Normal User: Can view if scan belongs to their shift.
        """
        scan = await self.repo.get_by_id(scan_id)
        if not scan:
            raise ScanNotFoundError(f"Scan record {scan_id} not found")

        if not self._is_admin(current_user) and not self._has_permission(current_user, Permission.SCANS_VIEW_ANY):
            await self._verify_scan_ownership(scan, current_user)

        return self._to_dict(scan)

    async def list_scans(
        self,
        current_user: Dict[str, Any],
        shift_id: Optional[str | uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List scan records:
        - Admin or SCANS_VIEW_ANY:
            * If shift_id is provided, returns scans for that shift.
            * Otherwise returns all recent scans.
        - Normal User:
            * Default (no permissions needed): Returns their own scans across their shifts.
            * If shift_id provided, ensures they own that shift.
        """
        is_privileged = self._is_admin(current_user) or self._has_permission(
            current_user, Permission.SCANS_VIEW_ANY
        )
        user_id = self._get_user_id(current_user)

        if shift_id:
            shift = await self.shift_repo.get_by_id(shift_id)
            if not shift:
                raise ShiftNotFoundError(f"Shift {shift_id} not found")

            if not is_privileged and shift.user_id != user_id:
                raise PermissionDeniedError("You do not have access to view scans for this shift")

            scans = await self.repo.get_by_shift(
                shift_id=shift_id, status=status, limit=limit, offset=offset
            )
        elif is_privileged:
            scans = await self.repo.get_recent_scans(status=status, limit=limit)
        else:
            # Normal user default view: Their own scan history
            scans = await self.repo.get_by_user(
                user_id=user_id, status=status, limit=limit, offset=offset
            )

        return {
            "items": [self._to_dict(s) for s in scans],
            "limit": limit,
            "offset": offset,
            "total": len(scans),
        }

    async def get_shift_metrics(
        self, shift_id: str | uuid.UUID, current_user: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retrieve aggregated metrics (valid vs invalid counts) for a shift."""
        shift = await self.shift_repo.get_by_id(shift_id)
        if not shift:
            raise ShiftNotFoundError(f"Shift {shift_id} not found")

        is_privileged = self._is_admin(current_user) or self._has_permission(
            current_user, Permission.SCANS_VIEW_ANY
        )
        user_id = self._get_user_id(current_user)
        if not is_privileged and shift.user_id != user_id:
            raise PermissionDeniedError("You do not have access to metrics for this shift")

        return await self.repo.get_shift_metrics(shift_id)

    async def search_by_claim(
        self,
        claim_key: str,
        expected_value: Any,
        current_user: Dict[str, Any],
        shift_id: Optional[str | uuid.UUID] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search scans matching a JSONB claim key-value pair."""
        is_privileged = self._is_admin(current_user) or self._has_permission(
            current_user, Permission.SCANS_VIEW_ANY
        )
        if not is_privileged:
            raise PermissionDeniedError("Admin or SCANS_VIEW_ANY permission is required to search claim logs")

        scans = await self.repo.search_by_jwt_claim(
            claim_key=claim_key,
            expected_value=expected_value,
            shift_id=shift_id,
            limit=limit,
        )
        return [self._to_dict(s) for s in scans]

    # ================================================================
    # WRITE & INGEST OPERATIONS
    # ================================================================
    async def record_scan(
        self,
        shift_id: str | uuid.UUID,
        jwt_scanned: Dict[str, Any],
        status: str,
        scanned_at: datetime,
        current_user: Dict[str, Any],
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a single scan event during an active shift."""
        shift = await self.shift_repo.get_by_id(shift_id)
        if not shift:
            raise ShiftNotFoundError(f"Shift {shift_id} not found")

        user_id = self._get_user_id(current_user)
        if not self._is_admin(current_user) and shift.user_id != user_id:
            raise PermissionDeniedError("Cannot log scans to a shift owned by another user")

        if shift.status != "active":
            raise ValidationError(f"Cannot log scan: Shift {shift_id} status is '{shift.status}'")

        scan = await self.repo.create(
            shift_id=shift_id,
            jwt_scanned=jwt_scanned,
            status=status,
            scanned_at=scanned_at,
            reason=reason,
        )
        return self._to_dict(scan)

    async def bulk_sync_scans(
        self,
        shift_id: str | uuid.UUID,
        scans_data: List[Dict[str, Any]],
        current_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Batch ingest scans synced from offline devices.
        Validates shift ownership and status once per batch for maximum throughput.
        """
        shift = await self.shift_repo.get_by_id(shift_id)
        if not shift:
            raise ShiftNotFoundError(f"Shift {shift_id} not found")

        user_id = self._get_user_id(current_user)
        if not self._is_admin(current_user) and shift.user_id != user_id:
            raise PermissionDeniedError("Cannot sync scans to a shift owned by another user")

        if shift.status not in ("active", "completed"):
            raise ValidationError(f"Cannot sync scans: Shift {shift_id} status is '{shift.status}'")

        # Deduplicate against scans already persisted for this shift
        existing_scans = await self.repo.get_by_shift(shift_id, limit=1000)
        existing_signatures = set()
        for s in existing_scans:
            if isinstance(s.jwt_scanned, dict):
                sig = s.jwt_scanned.get("jti") or s.jwt_scanned.get("raw_token") or str(s.scanned_at)
            else:
                sig = str(s.jwt_scanned)
            existing_signatures.add(sig)

        unique_scans = []
        for item in scans_data:
            item["shift_id"] = shift_id
            
            # Ensure scanned_at is a datetime object for asyncpg
            raw_scanned_at = item.get("scanned_at")
            if isinstance(raw_scanned_at, str):
                try:
                    item["scanned_at"] = datetime.fromisoformat(raw_scanned_at)
                except Exception:
                    item["scanned_at"] = datetime.now(timezone.utc)
            elif not raw_scanned_at:
                item["scanned_at"] = datetime.now(timezone.utc)

            if isinstance(item.get("jwt_scanned"), dict):
                sig = item["jwt_scanned"].get("jti") or item["jwt_scanned"].get("raw_token") or str(item.get("scanned_at"))
            else:
                sig = str(item.get("jwt_scanned"))
            if sig not in existing_signatures:
                unique_scans.append(item)
                existing_signatures.add(sig)

        created_scans = []
        if unique_scans:
            created_scans = await self.repo.bulk_create(unique_scans)

        logger.info(
            f"User {user_id} synced {len(created_scans)} new scans (skipped {len(scans_data) - len(unique_scans)} duplicates) for shift {shift_id}"
        )

        return {
            "shift_id": str(shift_id),
            "synced_count": len(created_scans),
            "skipped_duplicates": len(scans_data) - len(unique_scans),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    # ================================================================
    # UPDATE & DELETE OPERATIONS (PERMISSIONS-GATED)
    # ================================================================
    async def update_scan(
        self,
        scan_id: int,
        current_user: Dict[str, Any],
        status: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update a scan status or annotation.
        - Admin can update any scan.
        - Normal user must have SCANS_UPDATE permission and own the shift.
        """
        scan = await self.repo.get_by_id(scan_id)
        if not scan:
            raise ScanNotFoundError(f"Scan record {scan_id} not found")

        await self._verify_scan_ownership(scan, current_user, require_perm=Permission.SCANS_UPDATE)

        updated_scan = await self.repo.update(scan_id=scan_id, status=status, reason=reason)
        logger.info(f"Updated scan {scan_id} by user {self._get_user_id(current_user)}")
        return self._to_dict(updated_scan)

    async def delete_scan(
        self, scan_id: int, current_user: Dict[str, Any]
    ) -> bool:
        """
        Permanently delete a scan log.
        - Admin can delete any scan.
        - Normal user must have SCANS_DELETE permission and own the shift.
        """
        scan = await self.repo.get_by_id(scan_id)
        if not scan:
            raise ScanNotFoundError(f"Scan record {scan_id} not found")

        await self._verify_scan_ownership(scan, current_user, require_perm=Permission.SCANS_DELETE)

        result = await self.repo.delete(scan_id)
        logger.warning(f"Deleted scan {scan_id} by user {self._get_user_id(current_user)}")
        return result
