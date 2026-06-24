"""Generate tenant insights (recommendations + memos) from real data.

Aggregates the tenant's recent activity (sentiment, intents, backlog,
complaint themes, competitor + brand mentions) and asks the configured LLM
(settings.classifier_model — Llama in the sandbox, Claude for real clients)
to produce a lead + featured recommendations + memos in the `insights`
schema. Persisted by the worker, which replaces the tenant's prior insights.
"""
import json
import logging
from typing import Any, cast
from uuid import UUID

import asyncpg
import litellm

from setiq.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sos un analista de engagement para una plataforma que ayuda \
a marcas en Latinoamérica (Bolivia) a entender y responder las interacciones \
de su audiencia en redes sociales.

A partir del resumen de datos REALES de un tenant, generá insights accionables \
en español rioplatense-neutro boliviano. NO inventes números que no estén en el \
resumen. Sé concreto y útil. Fundamentá CADA insight citando números concretos del \
resumen (ej. "29 menciones negativas", "140 conversaciones sin resolver") dentro del \
body, impact o footnote — esa evidencia es obligatoria.

Devolvé SOLO un objeto JSON con esta forma exacta, sin texto adicional:
{
  "lead": {
    "title": "inicio del titular (termina con un espacio si sigue title_em)",
    "title_em": "fragmento del medio a resaltar que CONTINÚA la frase de title (déjalo null si no aplica)",
    "body": "2-3 oraciones explicando el insight principal",
    "confidence": "Alta" | "Media" | "Baja"
  },
  "featured": [
    {
      "title": "inicio de la recomendación (con espacio final si sigue)",
      "title_em": "fragmento resaltado que continúa la frase (o null)",
      "title_tail": "resto de la frase tras lo resaltado (o null)",
      "body": "1-2 oraciones", "impact": "Impacto: <breve>", "confidence": "Alta|Media|Baja",
      "action_label": "texto del botón", "action_route": "/inbox" | "/segmentos" | "/recomendaciones"
    }
  ],
  "memos": [
    {
      "tag": "Memo 01 · <tema>", "severity": "low" | "med" | "high",
      "title": "título corto", "body": "1-2 oraciones", "footnote": "Potencial: <breve>" | null
    }
  ]
}

Generá 1 lead, 2-3 featured y 3-4 memos. Ordená los memos del más importante al menos.

REGLA CLAVE de titulares: `title` + `title_em` + `title_tail` se CONCATENAN tal cual \
(incluí los espacios que correspondan) y deben leerse como UNA sola oración gramatical \
y correcta. `title_em` es sólo la parte del medio que se resalta — NO repitas texto entre \
los tres campos. Si no necesitás resaltar nada, poné `title_em` y `title_tail` en null y \
escribí el titular completo en `title`."""


async def _gather_context(conn: asyncpg.Connection, tenant_id: UUID) -> dict[str, Any]:
    sentiment = await conn.fetch(
        """
        WITH latest AS (
            SELECT DISTINCT ON (mc.message_id) mc.label
            FROM message_classifications mc
            JOIN messages m ON m.id = mc.message_id
            WHERE mc.tenant_id = $1 AND mc.kind = 'sentiment'
              AND m.sent_at > NOW() - INTERVAL '14 days'
            ORDER BY mc.message_id, mc.created_at DESC
        )
        SELECT label, COUNT(*) AS n FROM latest GROUP BY label ORDER BY n DESC
        """,
        tenant_id,
    )
    intents = await conn.fetch(
        """
        WITH latest AS (
            SELECT DISTINCT ON (mc.message_id) mc.label
            FROM message_classifications mc
            JOIN messages m ON m.id = mc.message_id
            WHERE mc.tenant_id = $1 AND mc.kind = 'intent'
              AND m.sent_at > NOW() - INTERVAL '14 days'
            ORDER BY mc.message_id, mc.created_at DESC
        )
        SELECT label, COUNT(*) AS n FROM latest GROUP BY label ORDER BY n DESC
        """,
        tenant_id,
    )
    backlog = await conn.fetchval(
        "SELECT COUNT(*) FROM conversations "
        "WHERE tenant_id = $1 AND status IN ('open', 'pending_agent')",
        tenant_id,
    )
    complaints = await conn.fetch(
        """
        SELECT DISTINCT m.content_text
        FROM messages m
        JOIN message_classifications mc ON mc.message_id = m.id
        WHERE mc.tenant_id = $1 AND mc.kind = 'intent' AND mc.label = 'complaint'
          AND m.content_text IS NOT NULL AND length(trim(m.content_text)) > 0
        ORDER BY m.content_text
        LIMIT 12
        """,
        tenant_id,
    )
    competitors = await conn.fetch(
        """
        SELECT ts.label, COUNT(mn.id) AS n
        FROM tracked_subjects ts
        LEFT JOIN mentions mn ON mn.tracked_subject_id = ts.id
            AND mn.content_published_at > NOW() - INTERVAL '14 days'
        WHERE ts.tenant_id = $1 AND ts.kind = 'competitor'
        GROUP BY ts.label ORDER BY n DESC LIMIT 6
        """,
        tenant_id,
    )
    return {
        "sentiment": {r["label"]: r["n"] for r in sentiment},
        "intents": {r["label"]: r["n"] for r in intents},
        "backlog_unresolved": backlog or 0,
        "complaint_samples": [r["content_text"] for r in complaints],
        "competitor_mentions_14d": {r["label"]: r["n"] for r in competitors},
    }


async def generate(conn: asyncpg.Connection, tenant_id: UUID, tenant_name: str) -> list[dict[str, Any]]:
    """Build context, call the LLM, and return insight rows ready to insert."""
    context = await _gather_context(conn, tenant_id)
    user_prompt = (
        f"Tenant: {tenant_name}\n\n"
        f"Resumen de datos (últimos 14 días):\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )
    response = await litellm.acompletion(
        model=settings.classifier_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1500,
        temperature=0.4,
    )
    body = (response.choices[0].message.content or "").strip()
    start, end = body.find("{"), body.rfind("}")
    if start != -1 and end != -1:
        body = body[start:end + 1]
    parsed = cast(dict[str, Any], json.loads(body))
    return _to_rows(parsed)


def _to_rows(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lead = parsed.get("lead")
    if isinstance(lead, dict):
        rows.append({
            "kind": "lead", "rank": 0,
            "title": lead.get("title", ""), "title_em": lead.get("title_em"),
            "title_tail": None, "body": lead.get("body", ""),
            "confidence": lead.get("confidence"), "severity": None, "tag": None,
            "age": None, "impact": None, "footnote": None, "actions": [],
        })
    for i, f in enumerate(parsed.get("featured") or []):
        if not isinstance(f, dict):
            continue
        actions = []
        if f.get("action_label"):
            actions.append({"label": f["action_label"], "route": f.get("action_route"), "variant": "primary"})
        rows.append({
            "kind": "featured", "rank": i,
            "title": f.get("title", ""), "title_em": f.get("title_em"),
            "title_tail": f.get("title_tail"), "body": f.get("body", ""),
            "confidence": f.get("confidence"), "severity": None, "tag": None,
            "age": "hoy", "impact": f.get("impact"), "footnote": None, "actions": actions,
        })
    for i, mm in enumerate(parsed.get("memos") or []):
        if not isinstance(mm, dict):
            continue
        rows.append({
            "kind": "memo", "rank": i,
            "title": mm.get("title", ""), "title_em": None, "title_tail": None,
            "body": mm.get("body", ""), "confidence": None,
            "severity": mm.get("severity"), "tag": mm.get("tag"),
            "age": None, "impact": None, "footnote": mm.get("footnote"), "actions": [],
        })
    return rows
