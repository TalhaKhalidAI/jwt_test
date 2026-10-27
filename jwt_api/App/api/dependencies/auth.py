# App/api/dependencies/auth.py
"""
Authentication and authorization dependencies.

Exception policy (applies to every function in this file):
    - Raise HTTPException only for HTTP-level DECISIONS (401/403/404).
      These are deliberate responses to a known condition, not caught
      exceptions. Example: "no token supplied" -> 401.
    - Let infrastructure errors (SQLAlchemyError, RedisError, library
      bugs, missing config) propagate to main.py's global handlers.
      Those handlers return a consistent 503 for DB/Redis downtime and
      a request_id-tagged 500 for genuine bugs.
    - Do NOT catch `Exception` anywhere in this file. Doing so hides
      the real cause and breaks the global handler contract.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from pathlib import Path
import uuid
from App.core.RedisConnector import redis_client
from App.core.redis_keys import revoked_shift_key
import jwt
from argon2 import PasswordHasher, exceptions as argon2_exceptions
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyCookie
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.settings import settings
from App.core.Connector import get_db
from App.repository.UserRepository import UserRepository
from App.core.LoggingInit import get_core_logger
from App.store import token_store
logger = get_core_logger(__name__)

# ============================================================================
# Password hasher
# ============================================================================
pwd_context = PasswordHasher(
    memory_cost=settings.MEMORY_COST,
    parallelism=settings.PARALLELISM,
    hash_len=settings.HASH_LENGTH,
    salt_len=settings.SALT_LENGTH,
)
# Timing-safe dummy hash for the "user not found" path in authenticate_user.
# Computed once at import so the code path is constant-time regardless of
# whether the user exists.
DUMMY_PASSWORD_HASH = pwd_context.hash("timing-safe-dummy-password")

# ============================================================================
# Security schemes
# ============================================================================
oauth2_scheme = HTTPBearer(auto_error=False)
cookie_scheme = APIKeyCookie(name="CSO", auto_error=False)
refresh_cookie_scheme = APIKeyCookie(name="refresh_token", auto_error=False)
shift_bearer_scheme = HTTPBearer(auto_error=False)


# ============================================================================
# Password functions
# ============================================================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against an Argon2 hash.

    Returns False on mismatch (the normal "wrong password" case).
    Any other failure (malformed hash, config error, library bug)
    propagates to main.py's handlers instead of being masked.
    """
    try:
        return pwd_context.verify(hash=hashed_password, password=plain_password)
    except argon2_exceptions.VerifyMismatchError:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password with Argon2."""
    return pwd_context.hash(password=password)


# ============================================================================
# Token functions
# ============================================================================
def _resolve_rsa_private_key(private_key: Optional[str] = None) -> str:
    """Resolve RSA private key from direct string, PEM file, or configured directory."""
    if private_key:
        return private_key

    pem_path = Path(settings.PEM_PATH) if settings.PEM_PATH else Path("./keys/")
    if pem_path.is_file():
        return pem_path.read_text(encoding="utf-8")

    for candidate in ("private.pem", "private_key.pem", "id_rsa"):
        key_file = pem_path / candidate
        if key_file.is_file():
            return key_file.read_text(encoding="utf-8")

    raise ValueError(
        f"RSA signing requested, but no private key provided and none found at '{pem_path}'"
    )


def _resolve_rsa_public_key(public_key: Optional[str] = None) -> str:
    """Resolve RSA public key from direct string, PEM file, or configured directory."""
    if public_key:
        return public_key

    pem_path = Path(settings.PEM_PATH) if settings.PEM_PATH else Path("./keys/")
    if pem_path.is_file():
        return pem_path.read_text(encoding="utf-8")

    for candidate in ("public.pem", "public_key.pem", "id_rsa.pub"):
        key_file = pem_path / candidate
        if key_file.is_file():
            return key_file.read_text(encoding="utf-8")

    raise ValueError(
        f"RSA verification requested, but no public key provided and none found at '{pem_path}'"
    )


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    rsa_enable: bool = False,
    private_key: Optional[str] = None,
    kid: Optional[str] = None,
) -> str:
    """
    Create a JWT access token.

    Supports both symmetric HS256 (default) and asymmetric RS256.
    Any failure propagates to main.py's handlers.
    """
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "jti": str(uuid.uuid4()),
    })

    if rsa_enable:
        pem_key = _resolve_rsa_private_key(private_key)
        headers = {"kid": kid} if kid else None
        encoded_jwt = jwt.encode(
            to_encode,
            pem_key,
            algorithm="RS256",
            headers=headers,
        )
    else:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key_str,
            algorithm=settings.ALGORITHM,
        )

    logger.debug(f"Created access token for user: {data.get('sub', 'unknown')}")
    return encoded_jwt


def decode_jwt(
    token: str,
    public_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT.

    Supports both HS256 and RS256 dynamically based on token header.
    - Expired signature  -> 401 "Token has expired"
    - Any other JWT issue -> 401 "Invalid token"

    Any non-JWT failure (missing SECRET_KEY, library bug) propagates.
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", settings.ALGORITHM)

        if alg.startswith("RS") or alg.startswith("PS"):
            key = _resolve_rsa_public_key(public_key)
            algorithms = [alg]
        else:
            key = settings.secret_key_str
            algorithms = [settings.ALGORITHM]

        payload = jwt.decode(
            token,
            key,
            algorithms=algorithms,
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.debug(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def decode_jwt_ignore_expiry(
    token: str,
    public_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT verifying the signature only -- used when we need to
    inspect claims (e.g. user_id) from an expired token.

    Returns None if the token is malformed. Any other failure propagates.
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", settings.ALGORITHM)

        if alg.startswith("RS") or alg.startswith("PS"):
            key = _resolve_rsa_public_key(public_key)
            algorithms = [alg]
        else:
            key = settings.secret_key_str
            algorithms = [settings.ALGORITHM]

        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT decode (ignore-expiry) failed: {e}")
        return None


# ============================================================================
# Shared token extraction / validation helpers
# ============================================================================
def _extract_token(
    credentials: Optional[HTTPAuthorizationCredentials],
    cookie_auth: Optional[str],
) -> str:
    """
    Return the bearer token from either the Authorization header or the
    auth cookie. Raises 401 if neither is present.
    """
    token = credentials.credentials if credentials else cookie_auth

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token found",
        )

    if token.startswith("Bearer "):
        token = token[7:]

    return token


async def _validate_token_payload(payload: Dict[str, Any]) -> None:
    """
    Shared post-decode validation for access tokens (both standard and SLT).

    - Rejects revoked tokens (Redis blocklist check).
    - Rejects non-access token types.
    - Rejects tokens missing `exp`.
    - Rejects expired tokens.
    - Rejects tokens missing `user_id`.

    Raises HTTPException(401) on any failure.
    NOTE: Redis errors propagate -- main.py returns 503 for those.
    """
    jti = payload.get("jti")
    if jti and await token_store.is_access_blocked(jti):
        logger.warning(f"Blocklisted token used: jti={jti}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_type = payload.get("type")
    if token_type != "access":
        logger.warning(f"Non-access token used for authentication: type={token_type!r}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. An access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    exp = payload.get("exp")
    if exp is None:
        logger.warning("Token has no expiration time")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has no expiration",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if datetime.fromtimestamp(exp, timezone.utc) <= datetime.now(timezone.utc):
        logger.warning(f"Expired token used: expired at {exp}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not payload.get("user_id"):
        logger.warning("Token missing user_id")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    iat = payload.get("iat")
    if user_id and iat:
        cutoff = await token_store.get_user_revocation_cutoff(user_id)
        if cutoff and iat < cutoff:
            logger.warning(f"Token revoked by user-level session revocation: user={user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

def _user_dict(user, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the auth context dictionary returned to route handlers."""
    return {
        "permissions": user.permissions,
        "id": user.id,
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.user_role,
        "is_active": user.is_active,
        "disabled": user.disabled,
        "token_type": payload.get("type"),
        "token_purpose": payload.get("purpose"),
        "types": payload.get("types"),
        "mfa_enabled": user.mfa_enabled,
        "mfa_method": getattr(user, "mfa_method", None),
        "jti": payload.get("jti"),
    }


# ============================================================================
# Dependencies -- SLT-aware (bypasses account-status checks)
# ============================================================================
async def get_current_user_slt(
    cookie_auth: Optional[str] = Depends(cookie_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Auth dependency that ACCEPTS short-lived tokens (SLT).

    SLT tokens bypass all account-status checks (disabled / deleted).
    Their purpose is account recovery and password reset.
    They expire in 2 minutes and are meant to be single-use.

    DB errors (OperationalError, SQLAlchemyError) are NOT caught here --
    they propagate to main.py's handlers, which return a consistent 503
    for every endpoint that depends on this function.
    """
    token = _extract_token(credentials, cookie_auth)

    payload = decode_jwt(token)

    await _validate_token_payload(payload)

    is_slt_token = payload.get("types") == "slts"

    repo = UserRepository(db)
    user = await repo.get_by_id(payload["user_id"])

    if not user:
        logger.warning(f"User not found for ID: {payload['user_id']}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # SLT tokens skip the disabled/deleted checks on purpose.
    if not is_slt_token:
        if user.is_deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        if user.disabled or not user.is_active:
            logger.warning(f"Inactive user tried to authenticate: {user.id}")
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Account is disabled or inactive. Contact admin.",
            )

    logger.debug(f"Authenticated user (SLT-allowed): {user.email} (ID: {user.id})")
    return _user_dict(user, payload)


# ============================================================================
# Dependencies -- standard access token only (SLT rejected)
# ============================================================================
async def get_current_user(
    cookie_auth: Optional[str] = Depends(cookie_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Standard auth dependency.

    - Requires a regular access token.
    - Rejects short-lived tokens (SLT).
    - Enforces account-status checks (disabled, deleted).

    DB errors propagate to main.py's handlers.
    """
    token = _extract_token(credentials, cookie_auth)

    payload = decode_jwt(token)

    await _validate_token_payload(payload)

    if payload.get("types") == "slts":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Short term token not allowed",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(payload["user_id"])

    if not user:
        logger.warning(f"User not found for ID in token: {payload['user_id']}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists",
        )

    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deleted",
        )

    if user.disabled or not user.is_active:
        logger.warning(f"Inactive user tried to authenticate: {user.id}")
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Account is disabled or inactive. Contact admin.",
        )

    logger.debug(f"Authenticated user: {user.email} (ID: {user.id})")
    return _user_dict(user, payload)


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Reject if the authenticated user is disabled or inactive."""
    if current_user.get("disabled") or not current_user.get("is_active"):
        logger.warning(f"Inactive user access attempted: {current_user.get('email')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Reject if the authenticated user is not an admin."""
    if current_user.get("role") != "admin":
        logger.warning(f"Non-admin user tried admin action: {current_user.get('email')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def get_current_user_optional(
    token: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[Dict[str, Any]]:
    """
    Optional auth. Returns the user if a valid token is present, else None.

    Only 401/403/404 from get_current_user are absorbed into None
    (that's the point of "optional"). Infrastructure errors still
    propagate -- a DB outage should not silently look like "anonymous".
    """
    if not token:
        return None

    try:
        return await get_current_user(credentials=token, db=db)
    except HTTPException:
        return None


# ============================================================================
# Helpers
# ============================================================================
async def authenticate_user(
    uname: str,
    password: str,
    db: AsyncSession,
) -> Optional[Dict[str, Any]]:
    """
    Authenticate by name OR email.

    Returns the user dict on success, None on any of:
      - user not found
      - wrong password
      - account disabled / inactive / deleted

    Infrastructure failures (SQLAlchemyError) propagate so main.py
    returns 503 instead of "invalid credentials".
    """
    repo = UserRepository(db)

    # Lookup. DB errors propagate -- do not catch.
    if "@" in uname:
        user = await repo.get_by_email(uname)
    else:
        user = await repo.get_by_name(uname)

    # Timing-safe: always run a hash comparison, even if the user is missing.
    if not user:
        logger.debug(f"Authentication failed: user not found - {uname}")
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, user.password_hash):
        logger.debug(f"Authentication failed: wrong password - {uname}")
        return None

    if user.disabled or not user.is_active:
        logger.debug(f"Authentication failed: account disabled - {uname}")
        return None

    if user.is_deleted:
        logger.debug(f"Authentication failed: account deleted - {uname}")
        return None

    logger.info(f"User authenticated successfully: {uname}")
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.user_role,
    }


def validate_password_strength(password: str) -> bool:
    """Check password strength (length + character classes)."""
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?`~"
    if not any(c in special_chars for c in password):
        return False
    return True


# ============================================================================
# Refresh token flow
# ============================================================================
def create_refresh_token(data: Dict[str, Any], family_id: str) -> str:
    """Create a refresh token with TTL configured via REFRESH_TOKEN_TTL_SECONDS."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(seconds=settings.REFRESH_TOKEN_TTL_SECONDS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "family": family_id,
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key_str,
        algorithm=settings.ALGORITHM,
    )
    logger.debug(f"Created refresh token for user: {data.get('sub', 'unknown')}")
    return encoded_jwt


async def refresh_access_token(refresh_token_value: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """
    Rotate a refresh token and issue new access + refresh tokens.

    Returns None if the token is revoked, expired, or user not found.
    Raises HTTPException for invalid token structure.
    """
    payload = decode_jwt(refresh_token_value)
    if not payload:
        return None

    jti = payload.get("jti")
    if not jti:
        return None

    # RT-04: Reuse detection revokes the entire family
    if await token_store.is_refresh_revoked(jti):
        logger.warning(f"Refresh token reuse detected: jti={jti}")
        family_id = payload.get("family")
        user_id = payload.get("user_id")
        if not family_id:
            rev_meta = await token_store.get_revoked_refresh_meta(jti)
            if rev_meta:
                family_id = rev_meta.get("family_id")
                user_id = rev_meta.get("user_id") or user_id
        if family_id:
            await token_store.revoke_family(family_id, user_id=user_id)
        return None

    # RT-06: Pre-validate in Redis before consuming so DB failure does not burn the token
    refresh_meta = await token_store.get_refresh(jti)
    if not refresh_meta:
        return None

    user_id = refresh_meta.get("user_id")
    family_id = refresh_meta.get("family_id")
    if not user_id:
        return None

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        return None

    # RT-05: Ensure deleted, disabled, or inactive users cannot refresh tokens
    if user.is_deleted or user.disabled or not user.is_active:
        logger.warning(f"Refresh attempted for inactive/disabled/deleted user: {user.id}")
        if family_id:
            await token_store.revoke_family(family_id, user_id=user_id)
        return None

    # Consume the old token now that DB checks have succeeded
    data = await token_store.consume_refresh(jti)
    if not data:
        return None

    access_token = create_access_token(
        data={
            "type": "token",
            "sub": user.email,
            "user_id": user.id,
            "name": user.name,
            "role": user.user_role,
        }
    )

    new_family_id = family_id or str(uuid.uuid4())
    refresh_token = create_refresh_token(
        data={
            "type": "rf_token",
            "sub": user.email,
            "user_id": user.id,
        },
        family_id=new_family_id,
    )

    new_jti = jwt.decode(
        refresh_token,
        settings.secret_key_str,
        algorithms=[settings.ALGORITHM],
    )["jti"]

    await token_store.store_refresh(
        jti=new_jti,
        user_id=user_id,
        family_id=new_family_id,
        ttl=settings.REFRESH_TOKEN_TTL_SECONDS,
    )
    await token_store.track_family_for_user(
        user_id=user_id,
        family_id=new_family_id,
        ttl=settings.REFRESH_TOKEN_TTL_SECONDS,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def create_short_live_token(user_id: int, db: AsyncSession, purpose: str = "account_restoration") -> str:
    """
    Create a short-lived token (SLT) for account recovery or password reset.
    Expires in 2 minutes.
    """
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    expire = datetime.now(timezone.utc) + timedelta(minutes=2)
    to_encode = {
        "sub": user.email,
        "user_id": user.id,
        "name": user.name,
        "role": user.user_role,
        "type": "access",
        "types": "slts",
        "purpose": purpose,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key_str,
        algorithm=settings.ALGORITHM,
    )
    logger.info(f"Created SLT for user {user_id}, purpose={purpose}")
    return encoded_jwt


async def get_current_shift_user(
    credentials: HTTPAuthorizationCredentials = Depends(shift_bearer_scheme)
):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Shift token required"
        )
        
    token = credentials.credentials
    
    try:
        # 1. Decode using the same secret key as your web login
        payload = jwt.decode(
            token, 
            settings.secret_key_str, 
            algorithms=[settings.ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Shift expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid shift token"
        )

    # 2. Ensure it's actually a shift token, not a standard web login token
    if payload.get("type") != "shift_token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid token type"
        )

    # 3. Check Redis to see if the Admin force-revoked this specific shift
    c = await redis_client.ensure_connected()
    if await c.exists(revoked_shift_key(payload.get("shift_id"))):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="This shift has been revoked by the admin"
        )

    # 4. Return the payload (user_id, role, shift_id)
    return payload

