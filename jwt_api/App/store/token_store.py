# App/store/token_store.py
import json
import time
from typing import Optional, List

from App.core.RedisConnector import redis_client
from App.core.redis_keys import (
    refresh_key,
    revoked_rt_key,
    family_key,
    blocklist_at_key,
    login_attempts_key,
    user_families_key,
)


def user_cutoff_key(user_id: int) -> str:
    return f"user_cutoff:{user_id}"


def login_attempts_account_key(email: str) -> str:
    return f"login_attempts:account:{email}"


# ========== REFRESH TOKENS ==========

async def store_refresh(jti: str, user_id: int, family_id: str, ttl: int) -> None:
    """Store refresh token metadata + track in family set + track family under user."""
    c = await redis_client.ensure_connected()
    pipe = c.pipeline()
    pipe.set(
        refresh_key(jti),
        json.dumps({"user_id": user_id, "family_id": family_id}),
        ex=ttl,
    )
    pipe.sadd(family_key(family_id), jti)
    pipe.expire(family_key(family_id), ttl)
    pipe.sadd(user_families_key(user_id), family_id)
    pipe.expire(user_families_key(user_id), ttl)
    await pipe.execute()


async def get_refresh(jti: str) -> Optional[dict]:
    """Retrieve refresh token metadata without deleting it."""
    c = await redis_client.ensure_connected()
    data = await c.get(refresh_key(jti))
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


async def consume_refresh(jti: str, revoke_ttl: int = 7 * 24 * 3600) -> Optional[dict]:
    """
    Atomic get+delete. Returns None if already used/expired.
    Leaves a revoked marker with family metadata so reuse revokes the family.
    """
    c = await redis_client.ensure_connected()
    data = await c.getdel(refresh_key(jti))
    if not data:
        return None
    parsed = json.loads(data)
    # Store metadata in the revoked marker for reuse detection
    revoked_payload = json.dumps({
        "family_id": parsed.get("family_id"),
        "user_id": parsed.get("user_id"),
    })
    await c.set(revoked_rt_key(jti), revoked_payload, ex=revoke_ttl)
    return parsed


async def get_revoked_refresh_meta(jti: str) -> Optional[dict]:
    """Retrieve metadata stored in a revoked refresh token marker."""
    c = await redis_client.ensure_connected()
    val = await c.get(revoked_rt_key(jti))
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None


async def revoke_refresh(jti: str, ttl: int) -> None:
    """Mark a refresh token as revoked and invalidate its stored payload immediately."""
    c = await redis_client.ensure_connected()
    await c.delete(refresh_key(jti))
    await c.set(revoked_rt_key(jti), "1", ex=ttl)


async def is_refresh_revoked(jti: str) -> bool:
    c = await redis_client.ensure_connected()
    return await c.exists(revoked_rt_key(jti)) == 1


async def revoke_family(
    family_id: str,
    user_id: Optional[int] = None,
    revoke_ttl: int = 7 * 24 * 3600,
) -> None:
    """Revoke every token belonging to this refresh family."""
    c = await redis_client.ensure_connected()
    jtis = await c.smembers(family_key(family_id))
    if jtis:
        pipe = c.pipeline()
        for j in jtis:
            pipe.delete(refresh_key(j))
            pipe.set(revoked_rt_key(j), "1", ex=revoke_ttl)
        pipe.delete(family_key(family_id))
        if user_id is not None:
            pipe.srem(user_families_key(user_id), family_id)
        await pipe.execute()


async def track_family_for_user(user_id: int, family_id: str, ttl: int) -> None:
    """Record that this family belongs to this user (used for logout-everywhere)."""
    c = await redis_client.ensure_connected()
    pipe = c.pipeline()
    pipe.sadd(user_families_key(user_id), family_id)
    pipe.expire(user_families_key(user_id), ttl)
    await pipe.execute()


async def get_user_families(user_id: int) -> List[str]:
    """Return every refresh family currently associated with this user."""
    c = await redis_client.ensure_connected()
    return list(await c.smembers(user_families_key(user_id)))


async def forget_family_for_user(user_id: int, family_id: str) -> None:
    """Remove a single family from the user's tracking set."""
    c = await redis_client.ensure_connected()
    await c.srem(user_families_key(user_id), family_id)


async def clear_user_families(user_id: int) -> None:
    """Delete the user's family-tracking set entirely."""
    c = await redis_client.ensure_connected()
    await c.delete(user_families_key(user_id))


# ========== ACCESS TOKEN BLOCKLIST & USER CUTOFF ==========

async def blocklist_access(jti: str, ttl: int) -> None:
    """Blocklist an access token jti until its natural expiry."""
    c = await redis_client.ensure_connected()
    await c.set(blocklist_at_key(jti), "1", ex=ttl)


async def is_access_blocked(jti: str) -> bool:
    c = await redis_client.ensure_connected()
    return await c.exists(blocklist_at_key(jti)) == 1


async def set_user_revocation_cutoff(user_id: int, ttl: int = 86400) -> None:
    """Set a timestamp cutoff. Any access token issued before this cutoff is invalid."""
    c = await redis_client.ensure_connected()
    await c.set(user_cutoff_key(user_id), str(time.time()), ex=ttl)


async def get_user_revocation_cutoff(user_id: int) -> Optional[float]:
    """Return timestamp cutoff for the user, or None."""
    c = await redis_client.ensure_connected()
    val = await c.get(user_cutoff_key(user_id))
    if not val:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ========== LOGIN RATE LIMITING ==========

async def check_login_rate(
    identifier: str,
    ip: str,
    max_attempts: int = 5,
    window: int = 300,
) -> bool:
    """
    Check if login is allowed without incrementing counter.
    Keyed on (normalized identifier, ip) and account-level bucket.
    """
    ident = (identifier or "").strip().lower()
    c = await redis_client.ensure_connected()
    key_ip = login_attempts_key(ident, ip)
    key_acc = login_attempts_account_key(ident)

    count_ip_raw = await c.get(key_ip)
    count_acc_raw = await c.get(key_acc)

    count_ip = int(count_ip_raw) if count_ip_raw else 0
    count_acc = int(count_acc_raw) if count_acc_raw else 0

    if count_ip >= max_attempts or count_acc >= (max_attempts * 3):
        return False
    return True


async def record_login_failure(
    identifier: str,
    ip: str,
    window: int = 300,
) -> None:
    """Increment failure counter upon failed credential verification."""
    ident = (identifier or "").strip().lower()
    c = await redis_client.ensure_connected()
    key_ip = login_attempts_key(ident, ip)
    key_acc = login_attempts_account_key(ident)

    pipe = c.pipeline()
    pipe.incr(key_ip)
    pipe.expire(key_ip, window)
    pipe.incr(key_acc)
    pipe.expire(key_acc, window)
    await pipe.execute()


async def reset_login_attempts(
    identifier: str,
    ip: str,
) -> None:
    """Reset attempt counters upon successful login."""
    ident = (identifier or "").strip().lower()
    c = await redis_client.ensure_connected()
    key_ip = login_attempts_key(ident, ip)
    key_acc = login_attempts_account_key(ident)
    pipe = c.pipeline()
    pipe.delete(key_ip)
    pipe.delete(key_acc)
    await pipe.execute()
