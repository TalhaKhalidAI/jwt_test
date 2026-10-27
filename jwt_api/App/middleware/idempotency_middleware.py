# App/middleware/idempotency_middleware.py
"""
Production-grade Idempotency Middleware.

Guarantees:
1. Keys are scoped by (Caller Identity, HTTP Method, Path, Client Key).
2. Request payload fingerprinting (SHA-256) rejects payload tampering/mismatches with 422.
3. Authentication and token issuance endpoints (/login, /logout, /refresh) are exempt to prevent token leaks.
4. Only cacheable success statuses (200, 201, 202, 204) are cached. Errors (401, 429, etc.) immediately release lock.
5. Preserves multiple Set-Cookie headers on original responses without dictionary collapsing.
6. Catches InfrastructureError (Redis down) and returns 503 with Retry-After.
"""
import hashlib
import json
from typing import Set
import jwt
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from App.store import idempotency_store
from App.core.exceptions import InfrastructureError
from App.core.LoggingInit import get_core_logger

logger = get_core_logger(__name__)

CACHEABLE_STATUS_CODES: Set[int] = {200, 201, 202, 204}
EXCLUDED_HEADERS: Set[str] = {
    "set-cookie",
    "authorization",
    "cookie",
    "content-length",
    "transfer-encoding",
    "connection",
}


def _is_exempt_route(path: str) -> bool:
    """
    Authentication, token issuance/refresh, and OTP verification endpoints
    must never be cached under idempotency keys to prevent token leaks.
    """
    normalized = path.rstrip("/").lower()
    exempt_keywords = (
        "/auth/basic_auth/login",
        "/auth/basic_auth/logout",
        "/users/users_config/refresh",
        "/mfa/verify",
        "/mfa/enroll",
        "/email_otp/verify",
    )
    return any(keyword in normalized for keyword in exempt_keywords)


def _extract_caller_identity(request: Request) -> str:
    """
    Derive caller identity to scope the idempotency key.
    Uses authenticated user ID if bearer token exists, otherwise falls back to client IP.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            sub = unverified.get("sub") or unverified.get("user_id")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "unknown"
    return f"ip:{client_ip}"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Only apply to mutating methods
        if request.method not in ["POST", "PUT", "PATCH"]:
            return await call_next(request)

        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return await call_next(request)

        # 2. Never cache authentication/session issuance endpoints
        if _is_exempt_route(request.url.path):
            return await call_next(request)

        # 3. Derive scoped key and payload fingerprint
        identity = _extract_caller_identity(request)
        scoped_key = f"{identity}:{request.method}:{request.url.path}:{idem_key}"

        request_body = await request.body()
        payload_hash = hashlib.sha256(request_body).hexdigest()

        # 4. Check Redis for existing record
        try:
            record = await idempotency_store.get_record(scoped_key)
        except InfrastructureError:
            return JSONResponse(
                status_code=503,
                content={"error": "service_unavailable", "message": "Idempotency store is temporarily unavailable."},
                headers={"Retry-After": "30"},
            )

        if record:
            cached_hash = record.get("payload_hash")
            # If payload differs, reject with 422
            if cached_hash and cached_hash != payload_hash:
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": "idempotency_payload_mismatch",
                        "message": "Idempotency-Key was reused with a different request payload.",
                    },
                )

            # In progress
            if record.get("state") == "processing":
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": "request_in_progress",
                        "message": "A request with this Idempotency-Key is currently processing.",
                    },
                )

            # Cached response replay
            if "status" in record and "body" in record:
                replay_headers = dict(record.get("headers", {}))
                replay_headers["X-Idempotency-Replay"] = "true"
                return Response(
                    content=record["body"],
                    status_code=record["status"],
                    headers=replay_headers,
                    media_type="application/json",
                )

        # 5. Acquire lock
        try:
            acquired = await idempotency_store.acquire_lock(scoped_key, payload_hash=payload_hash, lock_ttl=30)
        except InfrastructureError:
            return JSONResponse(
                status_code=503,
                content={"error": "service_unavailable", "message": "Idempotency store is temporarily unavailable."},
                headers={"Retry-After": "30"},
            )

        if not acquired:
            return JSONResponse(
                status_code=409,
                content={"error": "request_in_progress", "message": "Concurrent request detected."},
            )

        # 6. Process request
        try:
            response = await call_next(request)

            # 7. Consume response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            body_str = response_body.decode()

            # 8. Cache only successful responses (200, 201, 202, 204)
            if response.status_code in CACHEABLE_STATUS_CODES:
                safe_headers = {
                    k: v for k, v in response.headers.items()
                    if k.lower() not in EXCLUDED_HEADERS
                }
                try:
                    await idempotency_store.save_response(
                        scoped_key,
                        response.status_code,
                        body_str,
                        payload_hash=payload_hash,
                        headers=safe_headers,
                    )
                except InfrastructureError:
                    logger.warning(f"Failed to cache idempotency response for {scoped_key}")
            else:
                # Client error or server error: release lock immediately so client can retry
                try:
                    await idempotency_store.release_lock(scoped_key)
                except Exception:
                    pass

            # 9. Return response preserving raw headers (including multiple Set-Cookie)
            new_response = Response(
                content=response_body,
                status_code=response.status_code,
                media_type=response.media_type,
            )
            if hasattr(response, "raw_headers"):
                new_response.raw_headers = list(response.raw_headers)
            else:
                new_response.headers.update(response.headers)

            return new_response

        except Exception as e:
            # On unhandled error, release lock so key is not stuck for 30s
            try:
                await idempotency_store.release_lock(scoped_key)
            except Exception:
                pass
            raise e