# App/api/v1/CryptoKeys.py
"""
Cryptographic Key Management API Endpoints (Veriflow Asymmetric Keys).

Permissions & Authorization Rules:
    - Admin (role == "admin"): Can generate keys for any user (target_user_id), rotate,
      list all keys, revoke, and export private keys.
    - Normal User with KEYS_CREATE: Can generate keys ONLY for themselves. If they attempt
      to set target_user_id to another user, 403 Forbidden is returned.
    - Normal User with KEYS_VIEW: Can view safe public key metadata and listings.
    - Normal User with KEYS_REVOKE: Can revoke keys they are authorized to manage.
    - Public (Unauthenticated): Can access GET /keys/jwks to verify token signatures offline.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from App.core.Connector import get_db
from App.core.LoggingInit import get_core_logger
from App.core.exceptions import (
    CryptoKeyNotFoundError,
    DuplicateKeyIdError,
    InvalidCryptoKeyStateError,
    ValidationError,
    UserNotFoundError,
    PermissionDeniedError,
)
from App.models.Permissions import Permission
from App.api.dependencies.auth import get_current_user, verify_password
from App.api.dependencies.permissions import require_permission
from App.services.crypto_key_service import CryptoKeyService
from App.repository.UserRepository import UserRepository
from App.services.mfa_service import MFAService
from App.schemas.otp_purposes import OTPPurpose
from App.schemas.CryptoKeySchema import (
    CreateKeyRequest,
    RotateKeyRequest,
    RevokeKeyRequest,
    KeyResponse,
    KeyListResponse,
    JWKSResponse,
    IssueTokenRequest,
    IssueTokenResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
    GenerateProductTagQRRequest,
    ProductTagQRResponse,
    ExportPrivateKeyRequest,
)


logger = get_core_logger(__name__)
crypto_keys_router = APIRouter(prefix="/keys", tags=["Cryptographic Keys"])


# ============================================================================
# PUBLIC ENDPOINTS (UNAUTHENTICATED)
# ============================================================================
@crypto_keys_router.get(
    "/jwks",
    response_model=JWKSResponse,
    summary="Get active JSON Web Key Set (JWKS)",
    description="Public endpoint providing active RSA public keys. Used by scanners and Android clients to verify JWT signatures offline.",
)
async def get_jwks(db: AsyncSession = Depends(get_db)):
    service = CryptoKeyService(db)
    return await service.get_jwks()


# ============================================================================
# READ ENDPOINTS (KEYS_VIEW)
# ============================================================================
@crypto_keys_router.get(
    "/",
    response_model=KeyListResponse,
    summary="List cryptographic keys",
    description="Paginated list of cryptographic key pairs (safe public metadata only). Requires KEYS_VIEW permission.",
)
async def list_keys(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status ('active', 'revoked')"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.KEYS_VIEW], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = CryptoKeyService(db)
    return await service.list_keys(status=status_filter, limit=limit, offset=offset)


@crypto_keys_router.get(
    "/{key_id}",
    response_model=KeyResponse,
    summary="Get key by UUID",
    description="Fetch a single key pair by primary UUID (safe public view). Requires KEYS_VIEW permission.",
)
async def get_key_by_id(
    key_id: str,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.KEYS_VIEW], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = CryptoKeyService(db)
    try:
        return await service.get_key_by_id(key_id)
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@crypto_keys_router.get(
    "/kid/{kid}",
    response_model=KeyResponse,
    summary="Get key by Key ID (kid)",
    description="Point lookup for token verification by its Key ID. Requires KEYS_VIEW permission.",
)
async def get_key_by_kid(
    kid: str,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.KEYS_VIEW], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    service = CryptoKeyService(db)
    try:
        return await service.get_key_by_kid(kid)
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ============================================================================
# WRITE & LIFECYCLE ENDPOINTS (KEYS_CREATE, KEYS_UPDATE, KEYS_REVOKE)
# ============================================================================
@crypto_keys_router.post(
    "/",
    response_model=KeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new cryptographic keypair",
    description=(
        "Generates an RSA keypair in RAM, encrypts the private key with AES-256-GCM, "
        "and stores it in the database. "
        "Rule 1: Admins can assign the key to anyone (target_user_id). "
        "Rule 2: Normal users with KEYS_CREATE can only generate keys for themselves."
    ),
)
async def create_key(
    payload: CreateKeyRequest,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.KEYS_CREATE], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.get("role") == "admin"
    authenticated_user_id = current_user.get("user_id") or current_user.get("id")

    # Business Rule: Admin can make keys for anyone; normal users only for themselves
    if payload.target_user_id is not None:
        if not is_admin and payload.target_user_id != authenticated_user_id:
            logger.warning(
                f"Unauthorized key delegation: User {authenticated_user_id} tried to create key for user {payload.target_user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators are permitted to generate cryptographic keys for other users",
            )
        assigned_creator = payload.target_user_id
    else:
        assigned_creator = authenticated_user_id

    service = CryptoKeyService(db)
    try:
        return await service.create_key(
            name=payload.name,
            kid=payload.kid,
            key_size=payload.key_size,
            created_by=assigned_creator,
            assigned_permissions=payload.assigned_permissions,
            is_admin=is_admin,
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DuplicateKeyIdError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@crypto_keys_router.post(
    "/rotate",
    response_model=KeyResponse,
    summary="Rotate active cryptographic key",
    description="Generates a new active key pair that becomes the primary signing key. Requires KEYS_CREATE & KEYS_UPDATE.",
)
async def rotate_key(
    payload: RotateKeyRequest,
    current_user: Dict[str, Any] = Depends(
        require_permission(
            [Permission.KEYS_CREATE, Permission.KEYS_UPDATE], mode="all", bypass_admin=True
        )
    ),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.get("role") == "admin"
    authenticated_user_id = current_user.get("user_id") or current_user.get("id")

    if payload.target_user_id is not None and not is_admin:
        if payload.target_user_id != authenticated_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators are permitted to rotate keys for other users",
            )
        creator = payload.target_user_id
    else:
        creator = authenticated_user_id

    service = CryptoKeyService(db)
    try:
        return await service.rotate_key(
            name=payload.name,
            key_size=payload.key_size,
            created_by=creator,
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@crypto_keys_router.post(
    "/{key_id}/revoke",
    response_model=KeyResponse,
    summary="Revoke an active key",
    description="Revoke an active key with an audit reason. Requires KEYS_REVOKE permission.",
)
async def revoke_key(
    key_id: str,
    payload: RevokeKeyRequest,
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.KEYS_REVOKE], mode="any", bypass_admin=True)
    ),
    db: AsyncSession = Depends(get_db),
):
    authenticated_user_id = current_user.get("user_id") or current_user.get("id")
    service = CryptoKeyService(db)
    try:
        return await service.revoke_key(
            key_id=key_id,
            reason=payload.reason,
            revoked_by_user_id=authenticated_user_id,
        )
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidCryptoKeyStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@crypto_keys_router.post(
    "/{key_id}/export-private",
    summary="Export decrypted private key (Admin Only with Step-Up Auth)",
    description="High-security administrative operation to decrypt and export an RSA private key. Requires admin password and valid MFA code (if MFA is enabled on user account).",
)
@crypto_keys_router.get(
    "/{key_id}/export-private",
    summary="Export decrypted private key (Admin Only with Step-Up Auth)",
    include_in_schema=False,
)
async def export_private_key(
    key_id: str,
    payload: Optional[ExportPrivateKeyRequest] = None,
    password: Optional[str] = Query(None, description="Account password (for GET requests)"),
    otp: Optional[str] = Query(None, description="6-digit MFA OTP code (for GET requests)"),
    current_user: Dict[str, Any] = Depends(
        require_permission([Permission.KEYS_VIEW], mode="any", bypass_admin=False)
    ),
    db: AsyncSession = Depends(get_db),
):
    # Strict admin restriction
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators are authorized to export private key material",
        )

    authenticated_user_id = current_user.get("user_id") or current_user.get("id")
    repo = UserRepository(db)
    actor = await repo.get_by_id(authenticated_user_id)
    if not actor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")

    # Step 1: Password Verification (Always required for both MFA and non-MFA users)
    req_password = payload.password if payload and payload.password else password
    if not req_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account password is required to export private key",
        )
    if not verify_password(req_password, actor.password_hash):
        logger.warning(f"Failed password verification during private key export: actor={actor.id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid account password",
        )

    # Step 2: MFA Verification (Required ONLY if MFA is enabled on user account)
    if actor.mfa_enabled:
        req_otp = payload.otp if payload and payload.otp else otp
        if not req_otp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"MFA code required (method: {actor.mfa_method or 'totp'})",
                headers={
                    "X-MFA-Required": "true",
                    "X-MFA-Method": actor.mfa_method or "totp",
                },
            )
        mfa_service = MFAService(db)
        ok = await mfa_service.verify_code_for_actor(
            actor, req_otp.strip(), purpose=OTPPurpose.MFA_STEPUP.value
        )
        if not ok:
            logger.warning(f"Failed MFA verification during private key export: actor={actor.id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired MFA code",
            )

    service = CryptoKeyService(db)
    try:
        return await service.export_private_key(
            key_id=key_id,
            authorized_by_user_id=authenticated_user_id,
        )
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ============================================================================
# ASYMMETRIC (RS256) TOKEN OPERATIONS (MOBILE / ANDROID SIGNING & LOGIN)
# ============================================================================
@crypto_keys_router.post(
    "/tokens/issue",
    response_model=IssueTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue RS256 JWT using database RSA private key",
    description=(
        "Signs an RS256 JWT using the decrypted private PEM from the selected CryptoKey in PostgreSQL. "
        "Rule 1: Normal users can issue tokens for THEMSELVES. "
        "Rule 2: Admins can specify target_user_id to issue tokens for ANY user. "
        "Rule 3: If key_id is omitted, automatically signs with the latest active key."
    ),
)
async def issue_token(
    payload: IssueTokenRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CryptoKeyService(db)
    try:
        return await service.issue_asymmetric_token(
            current_user=current_user,
            target_user_id=payload.target_user_id,
            key_id=payload.key_id,
            expires_in_minutes=payload.expires_in_minutes,
            assigned_permissions=payload.assigned_permissions,
            extra_claims=payload.extra_claims,
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidCryptoKeyStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@crypto_keys_router.post(
    "/tokens/verify",
    response_model=VerifyTokenResponse,
    summary="Verify & decode an RS256 token via database public key",
    description=(
        "Extracts 'kid' from the unverified JWT header, fetches the matching public key "
        "from PostgreSQL, and verifies the RS256 signature and expiration."
    ),
)
async def verify_token(
    payload: VerifyTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    service = CryptoKeyService(db)
    try:
        return await service.verify_asymmetric_token(token=payload.token)
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidCryptoKeyStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@crypto_keys_router.post(
    "/tags/qr",
    summary="Generate RS256-signed product QR code tag",
    description=(
        "Signs arbitrary product claims with the selected CryptoKey's private key and "
        "dynamically generates a fitted QR code image. "
        "Rule 1: Admins can generate product tags for anyone and with any key. "
        "Rule 2: Normal users require 'tags.create' permission (and cannot set target_user_id for others). "
        "Rule 3: Expiration can be specified in minutes, hours, days, weeks, months, or years. "
        "Rule 4: Returns JSON with base64 Data URL or direct image/png download when format='png'."
    ),
)
async def generate_product_tag_qr(
    payload: GenerateProductTagQRRequest,
    qr_only: bool = Query(
        False,
        description="Checkbox: if checked (true), returns the QR code image (PNG) directly so it can be scanned from screen. If unchecked (false), returns raw JSON data.",
    ),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CryptoKeyService(db)
    try:
        result = await service.generate_product_tag_qr(
            current_user=current_user,
            payload_data=payload.payload,
            expires_in_value=payload.expires_in_value,
            expires_in_unit=payload.expires_in_unit.value,
            key_id=payload.key_id,
            box_size=payload.box_size,
            border=payload.border,
        )

        if qr_only or payload.format.lower() == "png":
            return Response(
                content=result["png_bytes"],
                media_type="image/png",
                headers={
                    "Content-Disposition": f'inline; filename="product_qr_tag_{result["kid"]}.png"'
                },
            )

        return ProductTagQRResponse(
            status="success",
            key_id=result["key_id"],
            kid=result["kid"],
            token=result["token"],
            qr_code_base64=result["qr_code_base64"],
            created_by=result["created_by"],
            created_by_email=result["created_by_email"],
            expires_at=result["expires_at"],
            expires_in_seconds=result["expires_in_seconds"],
            qr_version=result["qr_version"],
            payload=result["payload"],
        )

    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CryptoKeyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidCryptoKeyStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


