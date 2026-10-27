# App/store/idempotency_store.py
"""
Redis-backed store for Idempotency Keys.

Keys are prefixed with `idempotency:` and scoped by caller, method, and route.
State transitions:
  1. SET NX '{"state": "processing", "payload_hash": "..."}' (acquires lock, TTL 30s)
  2. SET '{"status": 200, "body": "...", "payload_hash": "...", "headers": {...}}' (replaces lock, TTL 24h)
"""
import json
from typing import Optional, Dict, Any
from redis.exceptions import RedisError

from App.core.RedisConnector import redis_client
from App.core.LoggingInit import get_core_logger
from App.core.exceptions import InfrastructureError
from App.core.redis_keys import idempotency_key

logger = get_core_logger(__name__)


def _key(scoped_key: str) -> str:
    """Helper to return the full Redis key."""
    return idempotency_key(scoped_key)


async def acquire_lock(scoped_key: str, payload_hash: str = "", lock_ttl: int = 30) -> bool:
    """
    Attempt to acquire the idempotency processing lock with a payload fingerprint.
    Returns True if acquired, False if already exists.
    """
    try:
        c = await redis_client.ensure_connected()
        lock_val = json.dumps({"state": "processing", "payload_hash": payload_hash})
        return bool(await c.set(_key(scoped_key), lock_val, ex=lock_ttl, nx=True))
    except (RedisError, ConnectionError, OSError) as e:
        logger.error(f"Redis error during idempotency acquire_lock: {e}")
        raise InfrastructureError("Redis unavailable for idempotency lock") from e


async def release_lock(scoped_key: str) -> None:
    """
    Release the lock if the request failed or was non-cacheable.
    Only deletes if currently in the 'processing' state to avoid clearing cached responses.
    """
    try:
        c = await redis_client.ensure_connected()
        current = await c.get(_key(scoped_key))
        if not current:
            return

        should_delete = False
        try:
            parsed = json.loads(current)
            if isinstance(parsed, dict) and parsed.get("state") == "processing":
                should_delete = True
        except (json.JSONDecodeError, TypeError):
            if current == "processing":
                should_delete = True

        if should_delete:
            await c.delete(_key(scoped_key))
    except (RedisError, ConnectionError, OSError) as e:
        logger.error(f"Redis error during idempotency release_lock: {e}")
        # Best-effort cleanup, do not crash on release


async def save_response(
    scoped_key: str,
    status_code: int,
    body: str,
    payload_hash: str = "",
    headers: Optional[Dict[str, str]] = None,
    ttl: int = 86400,
) -> None:
    """
    Save the final HTTP response along with request payload fingerprint.
    Default TTL is 24 hours.
    """
    try:
        c = await redis_client.ensure_connected()
        data = json.dumps({
            "status": status_code,
            "body": body,
            "payload_hash": payload_hash,
            "headers": headers or {},
        })
        await c.set(_key(scoped_key), data, ex=ttl)
        logger.info(f"Idempotency response cached: key={scoped_key} status={status_code}")
    except (RedisError, ConnectionError, OSError) as e:
        logger.error(f"Redis error during idempotency save_response: {e}")
        raise InfrastructureError("Redis unavailable for idempotency cache") from e


async def get_record(scoped_key: str) -> Optional[Dict[str, Any]]:
    """
    Returns the parsed JSON dictionary for the key if present, or None.
    """
    try:
        c = await redis_client.ensure_connected()
        raw = await c.get(_key(scoped_key))
        if not raw:
            return None
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Corrupt idempotency record for key: {scoped_key}")
        return None
    except (RedisError, ConnectionError, OSError) as e:
        logger.error(f"Redis error during idempotency get_record: {e}")
        raise InfrastructureError("Redis unavailable for idempotency get") from e


async def get_status(scoped_key: str) -> Optional[str]:
    """
    Backward-compatibility wrapper returning raw string or None.
    """
    try:
        c = await redis_client.ensure_connected()
        return await c.get(_key(scoped_key))
    except (RedisError, ConnectionError, OSError) as e:
        logger.error(f"Redis error during idempotency get_status: {e}")
        raise InfrastructureError("Redis unavailable for idempotency status") from e