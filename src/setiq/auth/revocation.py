import logging
import time

from setiq import queue

logger = logging.getLogger(__name__)

_PREFIX = "revoked_jti:"


async def revoke(jti: str, expires_at: int) -> None:
    if not jti:
        return
    ttl = max(expires_at - int(time.time()), 1)
    try:
        await queue.pool().set(_PREFIX + jti, "1", ex=ttl)
    except Exception:
        logger.exception("failed to revoke token %s", jti)


async def is_revoked(jti: str) -> bool:
    if not jti:
        return False
    try:
        return bool(await queue.pool().exists(_PREFIX + jti))
    except Exception:
        logger.exception("revocation check failed for %s", jti)
        return False
