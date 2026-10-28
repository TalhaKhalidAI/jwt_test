# App/services/crypto_key_service.py

from typing import Optional, List, Dict, Any
import uuid
import io
import base64
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from datetime import datetime, timedelta, timezone
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from App.services.base import BaseService
from App.repository.CryptoKeyRepository import CryptoKeyRepository
from App.repository.UserRepository import UserRepository
from App.repository.InventoryRuleRepository import InventoryRuleRepository
from App.core.rsa_crypto import RSAKeyGenerator
from App.core.aes_crypto import encrypt_data, decrypt_data
from App.core.settings import settings
from App.core.exceptions import (
    CryptoKeyNotFoundError,
    DuplicateKeyIdError,
    InvalidCryptoKeyStateError,
    PermissionDeniedError,
    ValidationError,
    UserNotFoundError,
)
from App.models.Permissions import Permission
from App.core.LoggingInit import get_core_logger

logger = get_core_logger(__name__)


class CryptoKeyService(BaseService):
    """
    Application business logic for Cryptographic Key operations (Veriflow Asymmetric Keys).

    Responsibilities:
        - Generate in-memory RSA keypairs via RSAKeyGenerator.
        - Encrypt private keys at rest using AES-256-GCM before DB persistence.
        - Decrypt private keys on-demand for signing operations and authorized key exports.
        - Issue RS256 JWT tokens using database private keys.
        - Verify RS256 JWT tokens dynamically against database public keys.
        - Expose safe public key sets (JWKS) for verification scanners and client apps.
        - Key lifecycle management: creation, rotation, revocation, and audit logs.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.db = db
        self.repo = CryptoKeyRepository(db)
        self.user_repo = UserRepository(db)
        self.rule_repo = InventoryRuleRepository(db)

    # ================================================================
    # SERIALIZATION HELPERS
    # ================================================================
    @staticmethod
    def _to_public_dict(key) -> Dict[str, Any]:
        """Convert a CryptoKey ORM model to a safe public dictionary (omits private key)."""
        return {
            "id": str(key.id),
            "name": key.name,
            "kid": key.kid,
            "public_key": key.public_key,
            "status": key.status,
            "created_by": key.created_by,
            "created_at": key.created_at.isoformat() if key.created_at else None,
            "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
            "revocation_reason": key.revocation_reason,
        }

    # ================================================================
    # KEY GENERATION & CREATION (CRUD: CREATE)
    # ================================================================
    async def create_key(
        self,
        name: str,
        kid: Optional[str] = None,
        key_size: int = 2048,
        created_by: Optional[int] = None,
        assigned_permissions: Optional[List[str]] = None,
        is_admin: bool = False,
    ) -> Dict[str, Any]:
        """
        Full lifecycle generation and storage of an RSA keypair:
        1. Generates an RSA keypair in RAM (2048/4096-bit).
        2. Encrypts the private key using AES-256-GCM via aes_crypto.
        3. Persists public key and encrypted private key into PostgreSQL.
        4. Optionally assigns permissions to the target user if called by an Admin.
        5. Returns safe public key metadata.

        Raises:
            ValidationError: If name or key_size is invalid.
            DuplicateKeyIdError: If kid already exists.
            PermissionDeniedError: If non-admin attempts to assign permissions.
        """
        if not name or not name.strip():
            raise ValidationError("Key name cannot be empty")

        if key_size < 2048:
            raise ValidationError("RSA key size must be at least 2048 bits")

        if assigned_permissions:
            if not is_admin:
                raise PermissionDeniedError("Only administrators are authorized to assign permissions to users")
            valid_perms = {p.value for p in Permission}
            invalid = [p for p in assigned_permissions if p not in valid_perms]
            if invalid:
                raise ValidationError(f"Invalid permissions specified: {', '.join(invalid)}")
            if created_by:
                perm_dict = {p: True for p in assigned_permissions}
                await self.user_repo.set_permissions(created_by, perm_dict)
                logger.info(f"Assigned permissions {assigned_permissions} to user {created_by} upon key creation")

        # 1. Generate RSA keypair in memory
        private_pem, public_pem = RSAKeyGenerator.generate(key_size=key_size)

        # 2. Derive or assign unique Key ID (kid)
        assigned_kid = kid.strip() if kid and kid.strip() else f"kid_{uuid.uuid4().hex[:16]}"

        # 3. Encrypt the private key at rest via AES-256-GCM
        private_key_encrypted = encrypt_data(private_pem)

        # 4. Store in database
        key = await self.repo.create(
            name=name.strip(),
            kid=assigned_kid,
            public_key=public_pem,
            private_key_encrypted=private_key_encrypted,
            created_by=created_by,
            status="active",
        )

        logger.info(
            f"Successfully generated and stored CryptoKey '{key.name}' (kid={key.kid}, id={key.id})"
        )
        return self._to_public_dict(key)

    # ================================================================
    # READ OPERATIONS (CRUD: READ)
    # ================================================================
    async def get_key_by_id(self, key_id: str | uuid.UUID) -> Dict[str, Any]:
        """Fetch a single key by UUID (safe public view)."""
        key = await self.repo.get_by_id(key_id)
        if not key:
            raise CryptoKeyNotFoundError(f"CryptoKey {key_id} not found")
        return self._to_public_dict(key)

    async def get_key_by_kid(self, kid: str) -> Dict[str, Any]:
        """Fetch a single key by Key ID (kid) for token verification."""
        key = await self.repo.get_by_kid(kid)
        if not key:
            raise CryptoKeyNotFoundError(f"CryptoKey with kid='{kid}' not found")
        return self._to_public_dict(key)

    async def list_keys(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Paginated list of keys for admin dashboard."""
        keys = await self.repo.list_keys(status=status, limit=limit, offset=offset)
        return {
            "items": [self._to_public_dict(k) for k in keys],
            "limit": limit,
            "offset": offset,
            "total": len(keys),
        }

    async def get_jwks(self) -> Dict[str, Any]:
        """
        Public endpoint payload (JWKS / Public Key Set).
        Used by Android scanners and client apps to verify JWT signatures offline.
        """
        active_keys = await self.repo.get_active_keys()
        return {
            "keys": [
                {
                    "kid": k.kid,
                    "kty": "RSA",
                    "alg": "RS256",
                    "use": "sig",
                    "public_key": k.public_key,
                }
                for k in active_keys
            ]
        }

    # ================================================================
    # SIGNING & PRIVATE KEY DECRYPTION (SECURE EXECUTION)
    # ================================================================
    async def get_active_signing_key(self) -> Dict[str, Any]:
        """
        Internal service method: Retrieve the latest active key with its
        decrypted private key for signing JWTs/tokens in memory.
        """
        key = await self.repo.get_latest_active_key()
        if not key:
            raise CryptoKeyNotFoundError(
                "No active cryptographic key available for signing operations"
            )

        # Decrypt private key in memory
        decrypted_private_pem = decrypt_data(key.private_key_encrypted)

        return {
            "id": str(key.id),
            "kid": key.kid,
            "name": key.name,
            "public_key": key.public_key,
            "private_key": decrypted_private_pem,
        }

    async def export_private_key(
        self,
        key_id: str | uuid.UUID,
        authorized_by_user_id: int,
    ) -> Dict[str, Any]:
        """
        High-security operation: Decrypt and export a private key PEM.
        Requires explicit administrative authorization and produces an audit log.
        """
        key = await self.repo.get_by_id(key_id)
        if not key:
            raise CryptoKeyNotFoundError(f"CryptoKey {key_id} not found")

        decrypted_private_pem = decrypt_data(key.private_key_encrypted)

        logger.warning(
            f"SECURITY AUDIT: Private key {key.id} (kid={key.kid}) was exported by user {authorized_by_user_id}"
        )
        return {
            "id": str(key.id),
            "kid": key.kid,
            "name": key.name,
            "private_key": decrypted_private_pem,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    # ================================================================
    # ROTATION & REVOCATION (CRUD: UPDATE / DELETE)
    # ================================================================
    async def rotate_key(
        self,
        name: str,
        key_size: int = 2048,
        created_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Rotate cryptographic keys:
        - Generates and persists a fresh active key pair.
        - The newly generated key immediately becomes the latest active signing key.
        - Previously existing active keys remain active for validating in-flight tokens.
        """
        new_key = await self.create_key(
            name=name,
            key_size=key_size,
            created_by=created_by,
        )
        logger.info(f"Key rotation completed. New primary signing key: kid={new_key['kid']}")
        return new_key

    async def revoke_key(
        self,
        key_id: str | uuid.UUID,
        reason: str = "Revoked by admin",
        revoked_by_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Revoke an active cryptographic key:
        - Updates status to 'revoked'.
        - Sets revocation timestamp and reason.
        - Prevents future signing and invalidates active tokens signed by this key.
        """
        if not reason or not reason.strip():
            raise ValidationError("Revocation reason must be provided")

        key = await self.repo.revoke(key_id=key_id, reason=reason.strip())

        logger.warning(
            f"Revoked CryptoKey {key.id} (kid={key.kid}) by user={revoked_by_user_id}. Reason: {reason}"
        )
        return self._to_public_dict(key)

    # ================================================================
    # ASYMMETRIC (RS256) TOKEN ISSUANCE & VERIFICATION
    # ================================================================
    async def issue_asymmetric_token(
        self,
        current_user: Dict[str, Any],
        target_user_id: Optional[int] = None,
        key_id: Optional[str | uuid.UUID] = None,
        expires_in_minutes: int = 60,
        assigned_permissions: Optional[List[str]] = None,
        extra_claims: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Issue an RS256 JWT access token signed by a database RSA private key.

        Rules:
            - Admins can issue tokens for ANY user (target_user_id) and optionally assign new permissions.
            - Normal users can only issue tokens for THEMSELVES and cannot assign/elevate permissions.
            - The user's active permissions dictionary is embedded into the 'permissions' claim of the JWT.
            - If key_id is omitted, the latest active key is automatically selected.
            - Private key is decrypted in volatile RAM only during signing.
        """
        auth_user_id = current_user.get("user_id") or current_user.get("id")
        is_admin = current_user.get("role") == "admin"

        # 1. Resolve Target User
        if target_user_id is not None and target_user_id != auth_user_id:
            if not is_admin:
                raise PermissionDeniedError(
                    "Only administrators are permitted to generate tokens on behalf of other users"
                )
            assigned_user_id = target_user_id
        else:
            assigned_user_id = auth_user_id

        # 2. Permission Assignment (Admin Only)
        if assigned_permissions:
            if not is_admin:
                raise PermissionDeniedError(
                    "Only administrators are authorized to assign or elevate user permissions"
                )
            valid_perms = {p.value for p in Permission}
            invalid = [p for p in assigned_permissions if p not in valid_perms]
            if invalid:
                raise ValidationError(f"Invalid permissions specified: {', '.join(invalid)}")
            perm_dict = {p: True for p in assigned_permissions}
            await self.user_repo.set_permissions(assigned_user_id, perm_dict)
            logger.info(
                f"Assigned permissions {assigned_permissions} to user {assigned_user_id} upon issuing asymmetric token"
            )

        user = await self.user_repo.get_by_id(assigned_user_id)
        if not user or user.is_deleted:
            raise UserNotFoundError(f"User {assigned_user_id} not found or inactive")

        # 3. Resolve Cryptographic Key
        if key_id:
            key = await self.repo.get_by_id(key_id)
            if not key:
                raise CryptoKeyNotFoundError(f"Cryptographic key {key_id} not found")
            if key.status != "active":
                raise InvalidCryptoKeyStateError(f"Key {key_id} status is '{key.status}', cannot sign tokens")
        else:
            key = await self.repo.get_latest_active_key()
            if not key:
                raise CryptoKeyNotFoundError("No active cryptographic key found to sign tokens")

        # 4. Decrypt Private Key in RAM
        private_pem = decrypt_data(key.private_key_encrypted)

        # 5. Resolve applicable inventory rules for this key
        applicable_rules = await self.rule_repo.get_applicable_rules(key_id=key.id)
        rules_dict = {r.matching_claim_key: r.expected_value for r in applicable_rules}

        # 6. Construct Payload & Sign
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=expires_in_minutes)
        user_perms = dict(user.permissions or {})
        user_perms.setdefault("scans.view.own", True)
        user_perms.setdefault("scans.create", True)
        user_perms.setdefault("inventory_rules.view", True)

        payload = {
            "sub": user.email,
            "user_id": user.id,
            "name": user.name,
            "role": user.user_role,
            "permissions": user_perms,
            "rules": rules_dict,
            "type": "access",
            "kid": key.kid,
            "iat": now,
            "exp": expires_at,
            "jti": str(uuid.uuid4()),
        }

        if extra_claims:
            for k, v in extra_claims.items():
                if k not in ("sub", "user_id", "name", "role", "permissions", "rules", "type", "iat", "exp", "kid"):
                    payload[k] = v

        encoded_jwt = jwt.encode(
            payload,
            private_pem,
            algorithm="RS256",
            headers={"kid": key.kid, "alg": "RS256", "typ": "JWT"},
        )

        logger.info(
            f"Issued RS256 token for user {user.id} ({user.email}) with {len(user_perms)} permissions and {len(rules_dict)} rules using key {key.id} (kid={key.kid})"
        )

        return {
            "access_token": encoded_jwt,
            "token_type": "bearer",
            "expires_in": expires_in_minutes * 60,
            "kid": key.kid,
            "key_id": str(key.id),
            "user_id": user.id,
        }

    async def verify_asymmetric_token(self, token: str) -> Dict[str, Any]:
        """
        Verify a JWT against keys stored in the database.
        - Supports RS256 using database public keys.
        - Resolves key from header 'kid', claims ('kid', 'key_id'), or latest active key.
        - Gracefully verifies standard HS256 tokens using the server secret key.
        - Verifies signature and expiration.
        """
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as e:
            raise ValidationError(f"Malformed token header: {e}")

        alg = unverified_header.get("alg", "RS256")

        # 1. Gracefully verify symmetric HS256 tokens
        if alg == "HS256":
            try:
                decoded_payload = jwt.decode(
                    token,
                    settings.secret_key_str,
                    algorithms=["HS256"],
                )
                return {
                    "is_valid": True,
                    "kid": "symmetric_hs256",
                    "key_name": "Server Secret Key (HS256)",
                    "payload": decoded_payload,
                }
            except jwt.ExpiredSignatureError:
                raise ValidationError("Token has expired")
            except jwt.InvalidTokenError as e:
                raise ValidationError(f"Invalid token signature or payload: {e}")

        if not alg.startswith("RS") and not alg.startswith("PS"):
            raise ValidationError(f"Invalid token algorithm: expected RS256 or HS256, got '{alg}'")

        # 2. Resolve RSA key: Header kid -> Payload kid -> Payload key_id -> Latest active key
        kid = unverified_header.get("kid")
        key = None

        if kid:
            key = await self.repo.get_by_kid(kid)

        if not key:
            try:
                unverified_payload = jwt.decode(token, options={"verify_signature": False})
                claim_kid = unverified_payload.get("kid")
                claim_key_id = unverified_payload.get("key_id")
                if claim_kid:
                    key = await self.repo.get_by_kid(claim_kid)
                if not key and claim_key_id:
                    key = await self.repo.get_by_id(claim_key_id)
            except Exception:
                pass

        if not key:
            key = await self.repo.get_latest_active_key()

        if not key:
            raise CryptoKeyNotFoundError(
                f"No matching active cryptographic key found to verify token (kid={kid})"
            )

        if key.status != "active":
            raise InvalidCryptoKeyStateError(f"Key with kid='{key.kid}' has been revoked or is inactive")

        try:
            decoded_payload = jwt.decode(
                token,
                key.public_key,
                algorithms=[alg],
            )
        except jwt.ExpiredSignatureError:
            raise ValidationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValidationError(f"Invalid token signature or payload: {e}")

        return {
            "is_valid": True,
            "kid": key.kid,
            "key_name": key.name,
            "payload": decoded_payload,
        }

    async def generate_product_tag_qr(
        self,
        current_user: Dict[str, Any],
        payload_data: Dict[str, Any],
        expires_in_value: int = 30,
        expires_in_unit: str = "days",
        key_id: Optional[str | uuid.UUID] = None,
        box_size: int = 10,
        border: int = 4,
    ) -> Dict[str, Any]:
        """
        Generate an RS256-signed Product Tag JWT and render it into a dynamically fitted QR code.

        Creator Attribution:
            - The tag is ALWAYS stamped with the authenticated user who created it (user_id, created_by, created_by_email, creator_name).

        Permissions:
            - Admins (role == "admin"): Can generate product tags with any key.
            - Normal users: Must have 'tags.create' (or 'keys.create' / 'inventory_rules.create') permission.

        Features:
            - Flexible expiration units: minutes, hours, days, weeks, months, years.
            - Embeds custom user-provided attributes (SKU, product_id, batch_no, warehouse, etc.).
            - QR code dimension dynamically adapts to fit the complete JWT data size.
        """
        auth_user_id = current_user.get("user_id") or current_user.get("id")
        is_admin = current_user.get("role") == "admin"
        if not auth_user_id:
            raise PermissionDeniedError("Could not determine authenticated user ID from token")

        user = await self.user_repo.get_by_id(auth_user_id)
        if not user or user.is_deleted:
            raise UserNotFoundError(f"User {auth_user_id} not found or inactive")

        user_perms = current_user.get("permissions") or {}
        if isinstance(user.permissions, dict):
            user_perms = {**user.permissions, **user_perms}

        # 1. Permission Gate
        has_permission = (
            is_admin
            or user_perms.get(Permission.TAGS_CREATE.value) is True
            or user_perms.get(Permission.KEYS_CREATE.value) is True
            or user_perms.get(Permission.INVENTORY_RULES_CREATE.value) is True
            or user_perms.get("*") is True
        )
        if not has_permission:
            raise PermissionDeniedError(
                "You are not authorized to generate product tag QR codes (requires 'tags.create' permission or Admin role)"
            )


        # 3. Cryptographic Key Resolution
        if key_id:
            key = await self.repo.get_by_id(key_id)
            if not key:
                raise CryptoKeyNotFoundError(f"Cryptographic key {key_id} not found")
            if key.status != "active":
                raise InvalidCryptoKeyStateError(f"Key {key_id} status is '{key.status}', cannot sign tokens")
        else:
            key = await self.repo.get_latest_active_key()
            if not key:
                raise CryptoKeyNotFoundError("No active cryptographic key found to sign product tag tokens")

        # 4. Decrypt Private RSA Key in RAM
        private_pem = decrypt_data(key.private_key_encrypted)

        # 5. Calculate Flexible Expiration
        unit_clean = str(expires_in_unit).lower().strip()
        if unit_clean in ("min", "minute", "minutes"):
            exp_seconds = expires_in_value * 60
        elif unit_clean in ("hour", "hours", "hr", "hrs"):
            exp_seconds = expires_in_value * 3600
        elif unit_clean in ("day", "days", "d"):
            exp_seconds = expires_in_value * 86400
        elif unit_clean in ("week", "weeks", "w"):
            exp_seconds = expires_in_value * 7 * 86400
        elif unit_clean in ("month", "months", "mo"):
            exp_seconds = expires_in_value * 30 * 86400
        elif unit_clean in ("year", "years", "yr", "yrs"):
            exp_seconds = expires_in_value * 365 * 86400
        else:
            raise ValidationError(
                f"Invalid expiration unit '{expires_in_unit}'. Supported: minutes, hours, days, weeks, months, years"
            )

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=exp_seconds)

        # 6. Build JWT Claims with Creator Attribution
        jwt_claims = {
            "iss": "veriflow-api",
            "sub": user.email,
            "user_id": user.id,
            "created_by": user.id,
            "created_by_email": user.email,
            "creator_name": user.name,
            "type": "product_tag",
            "kid": key.kid,
            "key_id": str(key.id),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": str(uuid.uuid4()),
        }

        # Embed custom user payload
        for k, v in payload_data.items():
            if k not in ("iss", "sub", "iat", "exp", "jti", "kid", "key_id"):
                jwt_claims[k] = v

        # 7. Sign RS256 JWT
        encoded_jwt = jwt.encode(
            jwt_claims,
            private_pem,
            algorithm="RS256",
            headers={"kid": key.kid, "alg": "RS256", "typ": "JWT"},
        )

        # 8. Render Dynamic QR Code (Auto-sized according to JWT length)
        qr = qrcode.QRCode(
            version=None,  # Automatically chooses smallest suitable QR version (1 to 40)
            error_correction=ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(encoded_jwt)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        png_bytes = buffer.getvalue()
        qr_b64 = base64.b64encode(png_bytes).decode("utf-8")
        qr_data_url = f"data:image/png;base64,{qr_b64}"

        logger.info(
            f"Generated product tag QR created by user {user.id} ({user.email}) using key {key.id} (kid={key.kid}). "
            f"QR version={qr.version}, token length={len(encoded_jwt)} bytes"
        )

        return {
            "key_id": str(key.id),
            "kid": key.kid,
            "token": encoded_jwt,
            "png_bytes": png_bytes,
            "qr_code_base64": qr_data_url,
            "created_by": user.id,
            "created_by_email": user.email,
            "expires_at": expires_at,
            "expires_in_seconds": exp_seconds,
            "qr_version": qr.version,
            "payload": jwt_claims,
        }



