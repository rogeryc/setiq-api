"""Message classification: take a message text, return labels.

A single LLM call returns sentiment + intent + priority + opportunity +
language. We persist one row per (item, kind) so dashboards can query each
label independently and we can re-classify with a new model/prompt later
without losing history.

The model is configurable via `settings.classifier_model` (LiteLLM format),
so the sandbox can run a free model (e.g. groq/moonshotai/kimi-k2-instruct)
and real clients run Claude (anthropic/claude-haiku-4-5). Provider keys are
read from the environment (GROQ_API_KEY, ANTHROPIC_API_KEY, ...).
"""
import json
import logging
from typing import Any, cast

import litellm

from setiq.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are classifying a customer message for a social-media \
customer-engagement platform serving brands in Latin America.

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


async def classify_text(text: str) -> dict[str, Any]:
    """Send text to the configured LLM and parse its JSON response. Raises on
    API failure or unparseable response."""
    response = await litellm.acompletion(
        model=settings.classifier_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        max_tokens=300,
        temperature=0,
    )
    body = (response.choices[0].message.content or "").strip()
    start, end = body.find("{"), body.rfind("}")
    if start != -1 and end != -1:
        body = body[start:end + 1]
    try:
        return cast(dict[str, Any], json.loads(body))
    except json.JSONDecodeError as e:
        logger.error("classifier returned non-JSON: %r", body)
        raise ValueError(f"classifier response is not valid JSON: {e}") from e


def model_info() -> tuple[str, str]:
    """Return (model_name, model_version) used for persistence."""
    return settings.classifier_model, ""
