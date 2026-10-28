# App/services/shift_service.py

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import uuid
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from App.services.base import BaseService
from App.repository.ShiftRepository import ShiftRepository
from App.repository.CryptoKeyRepository import CryptoKeyRepository
from App.repository.UserRepository import UserRepository
from App.core.settings import settings
from App.core.aes_crypto import decrypt_data
from App.core.RedisConnector import redis_client
from App.core.redis_keys import revoked_shift_key
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
from App.core.LoggingInit import get_core_logger

logger = get_core_logger(__name__)


class ShiftService(BaseService):
    """
    Application business logic for Shift (Session & Worker Floor Management) operations.

    Authorization Rules:
        - Admin (role == "admin"): Can start, checkout, revoke, and inspect shifts on ANY account.
        - Normal User (Default):
            * Can start a shift for THEMSELVES.
            * Can checkout of their OWN active shift.
            * Can view their OWN active shift and shift history.
            * CANNOT modify or delete shifts arbitrarily.
            * CANNOT revoke shifts (revocation is administrative).
        - Normal User with SHIFTS_REVOKE: Can administratively revoke active shifts.
        - Normal User with SHIFTS_VIEW: Can view other users' shifts.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.db = db
        self.repo = ShiftRepository(db)
        self.key_repo = CryptoKeyRepository(db)
        self.user_repo = UserRepository(db)

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

    @staticmethod
    def _to_dict(shift) -> Dict[str, Any]:
        return {
            "id": str(shift.id),
            "user_id": shift.user_id,
            "key_id": str(shift.key_id),
            "device_id": shift.device_id,
            "status": shift.status,
            "started_at": shift.started_at.isoformat() if shift.started_at else None,
            "expires_at": shift.expires_at.isoformat() if shift.expires_at else None,
            "ended_at": shift.ended_at.isoformat() if shift.ended_at else None,
            "revoked_reason": shift.revoked_reason,
        }

    def _generate_shift_token(self, shift, user, crypto_key) -> str:
        """
        Mint a scoped asymmetric (RS256) shift_token JWT for mobile scanner authorization.
        Decrypts the private key of the assigned CryptoKey in RAM to sign the token,
        and embeds user permissions, shift metadata, and key identifier (kid).
        """
        private_pem = decrypt_data(crypto_key.private_key_encrypted)
        user_perms = user.permissions or {}

        to_encode = {
            "sub": user.email,
            "user_id": user.id,
            "shift_id": str(shift.id),
            "key_id": str(shift.key_id),
            "kid": crypto_key.kid,
            "role": user.user_role,
            "permissions": user_perms,
            "type": "shift_token",
            "exp": shift.expires_at,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(
            to_encode,
            private_pem,
            algorithm="RS256",
            headers={"kid": crypto_key.kid, "alg": "RS256", "typ": "JWT"},
        )

    # ================================================================
    # SHIFT LIFECYCLE: START SHIFT
    # ================================================================
    async def start_shift(
        self,
        current_user: Dict[str, Any],
        target_user_id: Optional[int] = None,
        key_id: Optional[str | uuid.UUID] = None,
        duration_hours: int = 8,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start an active work shift.
        - Admin can start a shift for ANY user (target_user_id).
        - Normal user can only start a shift for THEMSELVES.
        - Automatically resolves active signing key if key_id is omitted.
        - Signs scoped RS256 shift_token JWT using the decrypted private key.
        - Embeds target user's active permissions into the token claims.
        - Returns shift details + scoped shift_token JWT for scanner verification.
        """
        auth_user_id = self._get_user_id(current_user)

        # Enforce user assignment rule
        if target_user_id is not None and target_user_id != auth_user_id:
            if not self._is_admin(current_user) and not self._has_permission(current_user, Permission.SHIFTS_CREATE):
                raise PermissionDeniedError("Only administrators can initiate shifts for other workers")
            assigned_user_id = target_user_id
        else:
            assigned_user_id = auth_user_id

        # Validate worker exists
        user = await self.user_repo.get_by_id(assigned_user_id)
        if not user or user.is_deleted:
            raise UserNotFoundError(f"User {assigned_user_id} not found or inactive")

        # Resolve Cryptographic Signing Key
        if key_id:
            crypto_key = await self.key_repo.get_by_id(key_id)
            if not crypto_key or crypto_key.status != "active":
                raise CryptoKeyNotFoundError(f"Cryptographic key {key_id} is not valid or active")
            assigned_key_id = crypto_key.id
        else:
            crypto_key = await self.key_repo.get_latest_active_key()
            if not crypto_key:
                raise CryptoKeyNotFoundError("No active cryptographic key available to assign to this shift")
            assigned_key_id = crypto_key.id

        if duration_hours < 1 or duration_hours > 24:
            raise ValidationError("Shift duration must be between 1 and 24 hours")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=duration_hours)

        shift = await self.repo.create_shift(
            user_id=assigned_user_id,
            key_id=assigned_key_id,
            expires_at=expires_at,
            device_id=device_id,
        )

        shift_token = self._generate_shift_token(shift, user, crypto_key)

        logger.info(f"Started shift {shift.id} for user {assigned_user_id} on device {device_id}")
        return {
            "shift": self._to_dict(shift),
            "shift_token": shift_token,
            "expires_at": expires_at.isoformat(),
        }

    # ================================================================
    # SHIFT LIFECYCLE: CHECKOUT
    # ================================================================
    async def checkout_shift(
        self,
        shift_id: str | uuid.UUID,
        current_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Normal checkout (end of workday).
        - Worker can checkout their own active shift.
        - Admin can checkout any worker's active shift.
        """
        shift = await self.repo.get_by_id(shift_id, for_update=True)
        if not shift:
            raise ShiftNotFoundError(f"Shift {shift_id} not found")

        auth_user_id = self._get_user_id(current_user)
        if not self._is_admin(current_user) and shift.user_id != auth_user_id:
            if not self._has_permission(current_user, Permission.SHIFTS_CHECKOUT):
                raise PermissionDeniedError("Cannot checkout a shift belonging to another user")

        completed_shift = await self.repo.complete_shift(shift_id)
        logger.info(f"Checked out shift {shift_id} by user {auth_user_id}")
        return self._to_dict(completed_shift)

    # ================================================================
    # SHIFT LIFECYCLE: REVOKE (ADMINISTRATIVE ACTION)
    # ================================================================
    async def revoke_shift(
        self,
        shift_id: str | uuid.UUID,
        reason: str,
        current_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Forcefully terminate an active shift immediately.
        - Marks shift status = 'revoked' in database.
        - Blacklists shift_id in Redis so mobile token verifiers reject it instantly.
        """
        if not self._is_admin(current_user) and not self._has_permission(current_user, Permission.SHIFTS_REVOKE):
            raise PermissionDeniedError("Administrative privileges or SHIFTS_REVOKE permission required")

        if not reason or not reason.strip():
            raise ValidationError("Revocation reason is required")

        revoked_shift = await self.repo.revoke_shift(shift_id, reason=reason.strip())

        # Blacklist in Redis
        try:
            c = await redis_client.ensure_connected()
            ttl = int((revoked_shift.expires_at - datetime.now(timezone.utc)).total_seconds())
            if ttl > 0:
                await c.set(revoked_shift_key(str(revoked_shift.id)), "revoked", ex=ttl)
        except Exception as e:
            logger.warning(f"Could not write revoked shift {shift_id} to Redis: {e}")

        logger.warning(
            f"Revoked shift {shift_id} by user {self._get_user_id(current_user)}. Reason: {reason}"
        )
        return self._to_dict(revoked_shift)

    # ================================================================
    # READ OPERATIONS
    # ================================================================
    async def get_shift_by_id(
        self,
        shift_id: str | uuid.UUID,
        current_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get shift details enforcing ownership."""
        shift = await self.repo.get_by_id(shift_id)
        if not shift:
            raise ShiftNotFoundError(f"Shift {shift_id} not found")

        auth_user_id = self._get_user_id(current_user)
        if not self._is_admin(current_user) and shift.user_id != auth_user_id:
            if not self._has_permission(current_user, Permission.SHIFTS_VIEW):
                raise PermissionDeniedError("You do not have permission to view this shift")

        return self._to_dict(shift)

    async def get_my_active_shift(self, current_user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Worker self-service lookup for their currently active shift."""
        user_id = self._get_user_id(current_user)
        shift = await self.repo.get_active_shift_by_user(user_id)
        return self._to_dict(shift) if shift else None

    async def list_shifts(
        self,
        current_user: Dict[str, Any],
        target_user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        List shift history:
        - Admin or SHIFTS_VIEW: Can view active shifts or query by target_user_id.
        - Normal user: Receives their OWN shift history.
        """
        is_privileged = self._is_admin(current_user) or self._has_permission(
            current_user, Permission.SHIFTS_VIEW
        )
        auth_user_id = self._get_user_id(current_user)

        if is_privileged and target_user_id is None:
            shifts = await self.repo.get_active_shifts(limit=limit, offset=offset)
        else:
            query_user_id = target_user_id if is_privileged and target_user_id else auth_user_id
            shifts = await self.repo.get_shifts_by_user(
                user_id=query_user_id, limit=limit, offset=offset
            )

        return {
            "items": [self._to_dict(s) for s in shifts],
            "limit": limit,
            "offset": offset,
            "total": len(shifts),
        }

    # ================================================================
    # EXPIRY MAINTENANCE
    # ================================================================
    async def expire_old_shifts(self, current_user: Dict[str, Any]) -> Dict[str, int]:
        """Admin or system background job to expire shifts past their expires_at date."""
        if not self._is_admin(current_user):
            raise PermissionDeniedError("Admin privileges required to trigger bulk shift expiry")

        count = await self.repo.expire_old_shifts()
        return {"expired_shifts_count": count}
