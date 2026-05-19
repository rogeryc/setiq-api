"""Claude classification: take a message text, return labels.

Single Claude call returns sentiment + intent + priority + opportunity +
language. We persist one row per (item, kind) so dashboards can query
each label independently and we can re-classify with a new model/prompt
later without losing history.
"""
import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

from setiq.config import settings

logger = logging.getLogger(__name__)

# Haiku 4.5 — cheapest of the current Claude family, plenty smart for this
# narrow classification task.
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are classifying a customer message for a social-media customer-engagement platform serving brands in Latin America.

Return ONLY a JSON object with these exact fields, no other text:
{
  "sentiment": "positive" | "neutral" | "negative",
  "sentiment_confidence": 0.0-1.0,
  "intent": "question" | "complaint" | "praise" | "purchase_intent" | "support_request" | "spam" | "other",
  "intent_confidence": 0.0-1.0,
  "priority": "low" | "medium" | "high" | "urgent",
  "opportunity": true | false,
  "language": "es" | "en" | "pt" | <other ISO 639-1>
}

Notes:
- "opportunity" is true if there's a commercial follow-up opportunity (buying intent, brand affinity, etc.).
- Confidence is your own subjective certainty, not statistical.
- Language is the language of the user's message, not the brand."""

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def classify_text(text: str) -> dict[str, Any]:
    """Send text to Claude, parse JSON response. Raises on API failure
    or unparseable response."""
    client = _get_client()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    body = response.content[0].text.strip()
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        logger.error("Claude returned non-JSON: %r", body)
        raise ValueError(f"Claude response is not valid JSON: {e}") from e


def model_info() -> tuple[str, str]:
    """Return (model_name, model_version) used for persistence."""
    # Anthropic doesn't expose a version separate from the dated model id,
    # so we put the date in version and the family in name.
    if "-" in MODEL:
        family, version = MODEL.rsplit("-", 1)
        return family, version
    return MODEL, ""
