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
from arq import cron

from setiq import db, queue
from setiq.ai import classifier, insights_generator

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


async def classify_mention(ctx: dict[str, Any], mention_id: str) -> None:
    """Read a mention's text, run the LLM, write mention_classifications."""
    mid = UUID(mention_id)
    async with db.admin_acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, tenant_id, content_text FROM mentions WHERE id = $1", mid
        )
        if row is None:
            logger.warning("classify_mention: mention %s not found", mention_id)
            return
        if not row["content_text"]:
            logger.info("classify_mention: mention %s has no text; skipping", mention_id)
            return
        try:
            result = await classifier.classify_text(row["content_text"])
        except Exception:
            logger.exception("classification failed for mention %s", mention_id)
            raise
        await _persist_mention(conn, row["tenant_id"], mid, result)
        logger.info("classified mention %s", mention_id)


def _classification_rows(result: dict[str, Any]) -> list[tuple[str, str, float | None]]:
    rows: list[tuple[str, str, float | None]] = []
    if "sentiment" in result:
        rows.append(("sentiment", str(result["sentiment"]), _conf(result.get("sentiment_confidence"))))
    if "intent" in result:
        rows.append(("intent", str(result["intent"]), _conf(result.get("intent_confidence"))))
    if "priority" in result:
        rows.append(("priority", str(result["priority"]), None))
    if "opportunity" in result:
        rows.append(("opportunity", "yes" if result["opportunity"] else "no", None))
    if "language" in result:
        rows.append(("language", str(result["language"]), None))
    return rows


async def _persist(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    message_id: UUID,
    result: dict[str, Any],
) -> None:
    model_name, model_version = classifier.model_info()
    for kind, label, confidence in _classification_rows(result):
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


async def _persist_mention(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    mention_id: UUID,
    result: dict[str, Any],
) -> None:
    model_name, model_version = classifier.model_info()
    for kind, label, confidence in _classification_rows(result):
        await conn.execute(
            """
            INSERT INTO mention_classifications (
                tenant_id, mention_id, kind, label, confidence,
                model_name, model_version, payload
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            tenant_id, mention_id, kind, label, confidence,
            model_name, model_version, result,
        )


def _conf(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return None


async def generate_insights(ctx: dict[str, Any], tenant_id: str) -> None:
    """Generate AI insights for one tenant and replace its current set."""
    tid = UUID(tenant_id)
    async with db.admin_acquire() as conn:
        tenant_name = await conn.fetchval("SELECT name FROM tenants WHERE id = $1", tid)
        if tenant_name is None:
            logger.warning("generate_insights: tenant %s not found", tenant_id)
            return
        rows = await insights_generator.generate(conn, tid, tenant_name)
        async with conn.transaction():
            await conn.execute(
                "UPDATE insights SET deleted_at = NOW() "
                "WHERE tenant_id = $1 AND deleted_at IS NULL",
                tid,
            )
            for r in rows:
                await conn.execute(
                    """
                    INSERT INTO insights (
                        tenant_id, kind, severity, tag, title, title_em, title_tail,
                        body, confidence, age, impact, footnote, actions, rank
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                    """,
                    tid, r["kind"], r["severity"], r["tag"], r["title"], r["title_em"],
                    r["title_tail"], r["body"], r["confidence"], r["age"], r["impact"],
                    r["footnote"], r["actions"], r["rank"],
                )
    logger.info("generate_insights: %d insights for tenant %s", len(rows), tenant_id)


async def generate_all_insights(ctx: dict[str, Any]) -> None:
    """Cron: enqueue insight generation for every active/trial tenant."""
    redis = ctx["redis"]
    async with db.admin_acquire() as conn:
        ids = await conn.fetch(
            "SELECT id FROM tenants WHERE status IN ('active', 'trial')"
        )
    for r in ids:
        await redis.enqueue_job("generate_insights", str(r["id"]))
    logger.info("generate_all_insights: enqueued %d tenants", len(ids))


async def cleanup_webhook_events(ctx: dict[str, Any]) -> None:
    """Hard-delete webhook_events older than 30 days. Runs daily via cron."""
    async with db.admin_acquire() as conn:
        result = await conn.execute(
            "DELETE FROM webhook_events WHERE received_at < NOW() - INTERVAL '30 days'"
        )
    logger.info("cleanup_webhook_events: %s", result)


async def startup(ctx: dict[str, Any]) -> None:
    await db.connect()


async def shutdown(ctx: dict[str, Any]) -> None:
    await db.disconnect()


class WorkerSettings:
    functions = [classify_message, classify_mention, generate_insights]
    cron_jobs = [
        cron(cleanup_webhook_events, hour=3, minute=0),
        cron(generate_all_insights, hour=4, minute=0),
    ]
    redis_settings = queue.redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 5
    job_timeout = 60  # seconds; Claude calls are fast (~1-3s)
