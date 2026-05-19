"""Arq worker entrypoint.

Run with:
    arq setiq.workers.runner.WorkerSettings

Lives as a separate process from the FastAPI app. Drains the
"classify_message" queue.
"""
import logging
from typing import Any
from uuid import UUID

import asyncpg

from setiq import db, queue
from setiq.ai import classifier

logger = logging.getLogger(__name__)


async def classify_message(ctx: dict[str, Any], message_id: str) -> None:
    """Read the message text, run Claude, write classifications.
    Idempotent on (message_id, kind) thanks to one-classification-per-kind
    rows (we just append; dashboards usually take the most recent)."""
    msg_uuid = UUID(message_id)
    async with db.admin_acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, tenant_id, content_text FROM messages WHERE id = $1",
            msg_uuid,
        )
        if row is None:
            logger.warning("classify: message %s not found", message_id)
            return
        if not row["content_text"]:
            logger.info("classify: message %s has no text; skipping", message_id)
            return

        try:
            result = await classifier.classify_text(row["content_text"])
        except Exception:
            logger.exception("Claude classification failed for %s", message_id)
            raise  # let arq retry

        await _persist(conn, row["tenant_id"], msg_uuid, result)
        logger.info("classified message %s: %s", message_id, result)


async def _persist(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    message_id: UUID,
    result: dict[str, Any],
) -> None:
    model_name, model_version = classifier.model_info()
    rows: list[tuple[str, str, float | None]] = []

    if "sentiment" in result:
        rows.append(("sentiment", str(result["sentiment"]),
                     _conf(result.get("sentiment_confidence"))))
    if "intent" in result:
        rows.append(("intent", str(result["intent"]),
                     _conf(result.get("intent_confidence"))))
    if "priority" in result:
        rows.append(("priority", str(result["priority"]), None))
    if "opportunity" in result:
        rows.append(("opportunity", "yes" if result["opportunity"] else "no", None))
    if "language" in result:
        rows.append(("language", str(result["language"]), None))

    for kind, label, confidence in rows:
        await conn.execute(
            """
            INSERT INTO message_classifications (
                tenant_id, message_id, kind, label, confidence,
                model_name, model_version, payload
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            tenant_id, message_id, kind, label, confidence,
            model_name, model_version, result,
        )


def _conf(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return None


async def startup(ctx: dict[str, Any]) -> None:
    await db.connect()


async def shutdown(ctx: dict[str, Any]) -> None:
    await db.disconnect()


class WorkerSettings:
    functions = [classify_message]
    redis_settings = queue.redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 5
    job_timeout = 60  # seconds; Claude calls are fast (~1-3s)
