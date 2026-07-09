"""Draft a reply for an operator: takes the conversation history + tenant
voice settings, returns a suggested reply text.

The draft is NEVER auto-sent. It lands in the composer for the agent to edit
and confirm — same review flow as before. Meta App Review specifically
expects human-in-the-loop for messaging permissions, and we want the same.

Uses the same LLM as the classifier (settings.classifier_model via LiteLLM),
so switching models across the platform is one env var. Runs off the same
GROQ_API_KEY / ANTHROPIC_API_KEY.
"""
import json
import logging
from typing import Any, cast

import litellm

from setiq.config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Sos un asistente que redacta borradores de respuestas para \
un agente humano que trabaja el inbox de una marca en redes sociales \
(Latinoamérica, principalmente Bolivia). Escribís en español rioplatense-neutro \
boliviano.

Vas a recibir:
  - El canal (instagram_comment, instagram_dm, facebook_comment, facebook_dm)
  - La conversación reciente (hasta 8 últimos mensajes, ordenados cronológicamente)
  - Preferencias de tono del inquilino (empático/profesional, comercial, etc.)

Devolvé SOLO un objeto JSON con este shape, sin texto adicional:
{
  "text": "el borrador de respuesta, listo para que el agente lo edite y envíe",
  "notes": "opcional: una línea de aclaración si necesitás avisar algo al agente (ej. 'sugiero verificar el número de lote antes de responder')"
}

REGLAS OBLIGATORIAS:
- La respuesta va DIRECTO al cliente, no al agente. Usá segunda persona ('vos' o 'usted' según el registro del canal).
- **Comentario público (channel termina en `_comment`)**: máximo 2-3 oraciones. Breve, contenida — otros lo van a leer.
- **DM privado (channel termina en `_dm`)**: puede ser más largo, hasta 4-5 oraciones. Se puede pedir detalles concretos (número de pedido, foto, etc.).
- NO uses emojis salvo que el último mensaje del cliente los use.
- NO prometas plazos concretos ni descuentos — usá lenguaje como "vamos a revisarlo" o "te vamos a responder en detalle por DM".
- Si el mensaje del cliente es spam o insulto sin contenido, devolvé `{"text": "", "notes": "El mensaje parece spam / insulto sin contenido genuino — sugerimos no responder o marcar como resuelto."}`.
- Si te falta contexto crítico para responder bien, redactalo igual pero pedile al cliente que amplíe (ej. "¿podés contarnos qué producto y qué fecha de compra?")."""


def _voice_preferences(ai_policy: dict[str, Any] | None) -> str:
    """Turn the tenant's ai_policy toggles into a short natural-language
    preference block for the prompt."""
    p = ai_policy or {}
    lines: list[str] = []
    if p.get("tone_empathetic", True):
        lines.append("- Tono empático y profesional (validá lo que siente el cliente antes de responder al contenido).")
    else:
        lines.append("- Tono directo, sin rodeos.")
    if p.get("generate_recs", True):
        lines.append("- Si tiene sentido, invitá suavemente a un canal comercial (newsletter, catálogo, DM) — pero sólo si el cliente muestra intención de compra.")
    lines.append("- No hables como bot ('estimado usuario', 'lamentamos las molestias'). Sonate humano.")
    return "\n".join(lines)


def _format_history(messages: list[dict[str, Any]]) -> str:
    """Render the last N messages as a compact chat log the LLM can read."""
    parts: list[str] = []
    for m in messages:
        who = "CLIENTE" if m["direction"] == "inbound" else "AGENTE"
        text = (m.get("content_text") or "").strip() or "(sin texto)"
        parts.append(f"[{who}] {text}")
    return "\n".join(parts)


async def draft(
    *,
    channel: str,
    messages: list[dict[str, Any]],
    ai_policy: dict[str, Any] | None,
    tenant_name: str | None = None,
) -> dict[str, Any]:
    """Ask the LLM to draft a reply for the given conversation.

    `messages` should be the last ~8 messages, cronologically. Only content_text
    + direction are used. Returns a dict with keys `text` (draft) and optional
    `notes` (agent-facing).
    """
    if not messages:
        raise ValueError("draft: at least one inbound message is required")

    voice = _voice_preferences(ai_policy)
    history = _format_history(messages[-8:])
    brand = tenant_name or "la marca"

    user_prompt = f"""Marca: {brand}
Canal: {channel}
Preferencias de tono:
{voice}

Conversación reciente (más antigua arriba, más reciente abajo):
{history}

Redactá un borrador de respuesta al último mensaje del CLIENTE."""

    response = await litellm.acompletion(
        model=settings.classifier_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=400,
        temperature=0.4,
    )
    body = (response.choices[0].message.content or "").strip()
    start, end = body.find("{"), body.rfind("}")
    if start != -1 and end != -1:
        body = body[start:end + 1]
    try:
        parsed = cast(dict[str, Any], json.loads(body))
    except json.JSONDecodeError as e:
        logger.error("reply_drafter returned non-JSON: %r", body)
        raise ValueError(f"drafter response is not valid JSON: {e}") from e

    text = str(parsed.get("text") or "").strip()
    notes = parsed.get("notes")
    return {
        "text": text,
        "notes": str(notes).strip() if notes else None,
    }
