"""Arq Redis pool used by the FastAPI app to enqueue background jobs.

The worker that drains these lives in `setiq.workers.runner`. Run it with:
    arq setiq.workers.runner.WorkerSettings
"""
import logging
from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from setiq.config import settings

logger = logging.getLogger(__name__)

_arq_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def connect() -> None:
    global _arq_pool
    _arq_pool = await create_pool(redis_settings())


async def disconnect() -> None:
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None


def pool() -> ArqRedis:
    if _arq_pool is None:
        raise RuntimeError("Arq pool not initialized")
    return _arq_pool


async def enqueue_classify_message(message_id: UUID) -> None:
    """Best-effort enqueue. If Redis is down we log and continue so the
    webhook still acknowledges to Meta."""
    try:
        await pool().enqueue_job("classify_message", str(message_id))
    except Exception:
        logger.exception("failed to enqueue classification for %s", message_id)
