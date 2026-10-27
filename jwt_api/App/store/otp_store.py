"""
Redis-backed email OTP store. Scoped by (email, purpose) so the same
user can have separate OTPs for "password_reset" and "login_2fa".
"""
import secrets
from typing import Optional

from App.core.RedisConnector import redis_client
from App.core.settings import settings
from App.core.LoggingInit import get_core_logger

logger = get_core_logger(__name__)


def mask_email(email: str) -> str:
    """Mask email for privacy in logs (e.g. j***n@example.com)."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _key(email: str, purpose: str) -> str:
    return f"email_otp:{purpose}:{email.lower()}"


def _attempts_key(email: str, purpose: str) -> str:
    return f"email_otp_attempts:{purpose}:{email.lower()}"


def _cooldown_key(email: str) -> str:
    return f"email_otp_cooldown:{email.lower()}"


async def check_and_set_cooldown(email: str, cooldown_seconds: int = 60) -> bool:
    """
    Check and set a dispatch cooldown to prevent email flooding.
    Returns True if allowed (cooldown acquired), False if on cooldown.
    """
    c = await redis_client.ensure_connected()
    return bool(await c.set(_cooldown_key(email), "1", ex=cooldown_seconds, nx=True))


async def create_otp(email: str, purpose: str) -> str:
    """Generate a 6-digit OTP, store, return it. Resets attempts counter."""
    otp = f"{secrets.randbelow(1_000_000):06d}"
    c = await redis_client.ensure_connected()
    await c.set(
        _key(email, purpose),
        otp,
        ex=settings.EMAIL_OTP_TTL_SECONDS,
    )
    await c.delete(_attempts_key(email, purpose))
    logger.info(f"Email OTP created for {mask_email(email)} purpose={purpose}")
    return otp


VERIFY_LUA = """
local stored = redis.call('GET', KEYS[1])
if not stored then
    return -1
end
local attempts = redis.call('INCR', KEYS[2])
if attempts == 1 then
    redis.call('EXPIRE', KEYS[2], tonumber(ARGV[2]))
end
if attempts > tonumber(ARGV[3]) then
    redis.call('DEL', KEYS[1])
    return -2
end
if stored == ARGV[1] then
    redis.call('DEL', KEYS[1])
    redis.call('DEL', KEYS[2])
    return 1
else
    return 0
end
"""


async def verify_otp(email: str, purpose: str, code: str) -> bool:
    """
    Atomically verify and consume on success. Bumps attempt counter on failure.
    Returns True only for a correct code that hasn't hit the attempt cap.
    """
    c = await redis_client.ensure_connected()
    otp_key = _key(email, purpose)
    attempts_key = _attempts_key(email, purpose)

    try:
        res = await c.eval(
            VERIFY_LUA,
            2,
            otp_key,
            attempts_key,
            code,
            str(settings.EMAIL_OTP_TTL_SECONDS),
            str(settings.EMAIL_OTP_MAX_ATTEMPTS),
        )
        # res: 1 = success, 0 = wrong code, -1 = expired/not found, -2 = max attempts
        if res == 1:
            logger.info(f"Email OTP verified: {mask_email(email)} purpose={purpose}")
            return True
        elif res == -2:
            logger.warning(f"Email OTP max attempts exceeded: {mask_email(email)} purpose={purpose}")
            return False
        else:
            return False
    except Exception:
        # Fallback if eval unsupported: safe getdel
        stored = await c.getdel(otp_key)
        if not stored:
            return False
        return secrets.compare_digest(stored, code)