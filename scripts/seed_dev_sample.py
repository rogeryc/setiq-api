"""Seed realistic sample data into Thalma's tenant.

Wipes and re-inserts:
  - 6 tracked_subjects (brand keywords + competitor handles)
  - ~40 contacts + their channel_identities
  - ~30 conversations across IG comments / IG DMs / FB comments /
    Messenger DMs / TikTok comments / email
  - ~120 messages with realistic Argentinian-Spanish content for a
    journalist's audience
  - ~120 message_classifications (sentiment, intent, priority,
    opportunity, language) — hand-set so dashboards have data without
    needing the Anthropic key
  - ~40 mentions (off-property posts mentioning Thalma or competitors)
  - ~40 mention_classifications

Idempotent: re-running fully resets the sample data for this tenant.
Run `scripts/seed_dev.py` first if the tenant doesn't exist yet.

Usage:
    python scripts/seed_dev_sample.py
"""
from __future__ import annotations

import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from setiq.config import settings  # noqa: E402

TENANT_SLUG = "thalma"

# Deterministic randomness so re-runs produce the same data.
random.seed(42)

NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

TRACKED_SUBJECTS: list[dict[str, Any]] = [
    {
        "kind": "brand",
        "label": "Thalma (marca propia)",
        "keywords": ["thalma", "thalma news", "thalma argentina"],
        "hashtags": ["thalma", "notathalma"],
        "handles": {},
    },
    {
        "kind": "competitor",
        "label": "Soledad Murillo",
        "keywords": [],
        "hashtags": [],
        "handles": {"instagram": "@solemurillo", "tiktok": "@solemurillo.ok", "facebook": "solemurillo"},
    },
    {
        "kind": "competitor",
        "label": "Diego Penna",
        "keywords": [],
        "hashtags": [],
        "handles": {"instagram": "@diegopenna", "tiktok": "@dpenna"},
    },
    {
        "kind": "competitor",
        "label": "La Trinchera (newsletter)",
        "keywords": [],
        "hashtags": [],
        "handles": {"instagram": "@latrinchera.news", "facebook": "latrinchera"},
    },
    {
        "kind": "keyword",
        "label": "Vivienda / alquileres",
        "keywords": ["vivienda", "alquileres", "ley de alquileres", "inquilinos"],
        "hashtags": ["alquileres", "leydealquileres"],
        "handles": {},
    },
    {
        "kind": "hashtag",
        "label": "Política provincial",
        "keywords": [],
        "hashtags": ["interior", "rosario", "cordoba", "provincias"],
        "handles": {},
    },
]


# (handle_on_ig, name, fb_handle_or_none, sentiment_lean)
CONTACTS: list[tuple[str, str, str | None, str]] = [
    ("maria_fan", "María González", "maria.gonzalez.bsas", "positive"),
    ("nico_c_arg", "Nicolás Cabrera", None, "positive"),
    ("luchitobsas", "Lucho B.", "lucho.b.aires", "neutral"),
    ("lectorosario", "El Lector de Rosario", None, "negative"),
    ("analiacba", "Analía Sosa", "analia.sosa.cba", "negative"),
    ("criticox", "El Crítico", None, "negative"),
    ("clara_fan_thalma", "Clara Méndez", "clara.mendez", "positive"),
    ("sofiacostas", "Sofía Costas", None, "positive"),
    ("juampi_ok", "Juan Pablo R.", "juampi.r", "neutral"),
    ("perezpaula", "Paula Pérez", None, "positive"),
    ("mateo.mza", "Mateo (Mendoza)", "mateomza", "neutral"),
    ("camilatuc", "Camila Tucumán", None, "positive"),
    ("luisbahia", "Luis (Bahía)", None, "neutral"),
    ("anto.f", "Antonella F.", "antonella.f", "positive"),
    ("ferpiri", "Fer Piriz", None, "positive"),
    ("emi_rosario", "Emi de Rosario", None, "negative"),
    ("malenaq", "Malena Q.", "malena.q.arg", "negative"),
    ("nahuel_lit", "Nahuel Litoral", None, "neutral"),
    ("marisamza", "Marisa M.", None, "negative"),
    ("vale.santafe", "Valeria (Santa Fe)", "vale.santafe", "neutral"),
    ("rodri.cordoba", "Rodrigo C.", None, "positive"),
    ("xime_estudia", "Ximena (estudiante)", None, "positive"),
    ("agus_v", "Agus V.", "agus.v.arg", "neutral"),
    ("flor.bbsas", "Flor B.", None, "positive"),
    ("damianp", "Damián P.", None, "negative"),
    ("luli.k", "Luli K.", "luli.k", "positive"),
    ("anonimo_42", "—", None, "negative"),  # anonymous
    ("anonimo_91", "—", None, "neutral"),
    ("tincho.b", "Martín B.", None, "neutral"),
    ("seba.r", "Sebastián R.", "seba.r.bsas", "positive"),
    ("nadia.s", "Nadia S.", None, "positive"),
    ("nora.f", "Nora F.", "nora.f", "negative"),
    ("franky", "Francisco (Franky)", None, "neutral"),
    ("majo.escribe", "Majo P.", "majo.escribe", "positive"),
    ("juli.rio", "Julián Río", None, "neutral"),
    ("dario.mendieta", "Darío Mendieta", "dario.mendieta", "positive"),
    ("yamila_m", "Yamila M.", None, "neutral"),
    ("carla.t", "Carla T.", "carla.t.arg", "positive"),
    ("pancho.alquila", "Pancho (alquiler)", None, "negative"),
    ("ines.l", "Inés L.", "ines.l", "positive"),
]


# Templates per (channel, intent, sentiment_lean) → list of message texts
# Keys: ("ig_comment"|"ig_dm"|"fb_comment"|"fb_dm"|"tiktok_comment"|"email", intent, sentiment)
TEMPLATES: dict[tuple[str, str], list[str]] = {
    ("praise", "positive"): [
        "Excelente nota como siempre 👏",
        "Esto es periodismo de verdad, gracias!",
        "Coincido totalmente, gracias por el trabajo",
        "Una de las mejores notas que leí este mes",
        "Gracias por meterte en este tema, hacía falta",
        "Te seguís ganando mi suscripción, una grosa",
    ],
    ("complaint", "negative"): [
        "Dejaste afuera el costo real en provincias.",
        "Mucha CABA y poca calle. La realidad acá es otra.",
        "Esa cifra no cierra, hablá con quien alquila en serio",
        "Sesgada hacia un solo lado, me decepcionó la nota",
        "Faltó la voz de quien alquila hace 5 años, no de un experto",
        "Esto es opinión disfrazada de investigación.",
    ],
    ("question", "neutral"): [
        "Cuándo publicás la siguiente parte?",
        "Tenés fuente para el dato del 38%? Me interesa citarlo",
        "Saldrá nota sobre vivienda en interior también?",
        "Hay versión en podcast de esta nota?",
        "Quién es la fuente del párrafo 3?",
    ],
    ("purchase_intent", "positive"): [
        "Cómo me suscribo al newsletter? Quiero pagar",
        "Pasame el link para apoyarte, me interesa",
        "Hay plan anual? Me sumo al pago",
        "Si hacés una serie completa pago entrada",
    ],
    ("support_request", "neutral"): [
        "No me llegó el último newsletter, podés revisar?",
        "El link al PDF está roto",
        "La app no me deja loguear desde ayer",
        "Cómo cambio el correo de la suscripción?",
    ],
    ("spam", "neutral"): [
        "🔥🔥🔥 visitanos en bit.ly/xxxx",
        "Gana 50.000 ARS por día desde casa - DM",
        "Hola hermosa, te escribo por DM",
    ],
    ("praise", "neutral"): [
        "Buena nota, interesante el ángulo",
        "Coincido con casi todo, lo voy a compartir",
    ],
}


# Conversation "themes" — title + channel + how many messages
CONVERSATION_THEMES: list[dict[str, Any]] = [
    {
        "channel": "instagram_comment",
        "thread_id": "ig_post_001_vivienda",
        "subject": "Comentarios en nota sobre vivienda",
        "default_intent_mix": [("complaint", "negative"), ("question", "neutral"), ("praise", "positive")],
        "n_contacts": 9,
        "n_messages": 22,
    },
    {
        "channel": "instagram_comment",
        "thread_id": "ig_post_002_alquileres",
        "subject": "Reel sobre ley de alquileres",
        "default_intent_mix": [("praise", "positive"), ("question", "neutral"), ("complaint", "negative")],
        "n_contacts": 7,
        "n_messages": 17,
    },
    {
        "channel": "instagram_dm",
        "thread_id": None,
        "subject": "DMs solicitando fuente",
        "default_intent_mix": [("question", "neutral"), ("purchase_intent", "positive")],
        "n_contacts": 5,
        "n_messages": 12,
    },
    {
        "channel": "instagram_comment",
        "thread_id": "ig_post_003_provincias",
        "subject": "Comentarios sobre cobertura del interior",
        "default_intent_mix": [("complaint", "negative"), ("praise", "positive")],
        "n_contacts": 6,
        "n_messages": 15,
    },
    {
        "channel": "tiktok_comment",
        "thread_id": "tt_video_2025_a",
        "subject": "Comentarios en TikTok (serie alquileres)",
        "default_intent_mix": [("praise", "positive"), ("question", "neutral"), ("praise", "positive")],
        "n_contacts": 8,
        "n_messages": 19,
    },
    {
        "channel": "facebook_comment",
        "thread_id": "fb_post_a",
        "subject": "Comentarios FB en nota de provincias",
        "default_intent_mix": [("complaint", "negative"), ("praise", "neutral")],
        "n_contacts": 5,
        "n_messages": 11,
    },
    {
        "channel": "facebook_dm",
        "thread_id": None,
        "subject": "DMs Messenger - soporte newsletter",
        "default_intent_mix": [("support_request", "neutral"), ("question", "neutral")],
        "n_contacts": 3,
        "n_messages": 8,
    },
    {
        "channel": "email",
        "thread_id": "newsletter_2026_05_001",
        "subject": "Newsletter — respuestas semana",
        "default_intent_mix": [("praise", "positive"), ("question", "neutral"), ("purchase_intent", "positive")],
        "n_contacts": 6,
        "n_messages": 16,
    },
]


# Off-property mentions (Apify-style scraped posts)
MENTIONS: list[dict[str, Any]] = [
    # Mentions of Thalma's brand on other people's content
    {"platform": "instagram", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@valentinaponce", "author_name": "Valentina Ponce",
     "text": "Justo hoy hablábamos de esto con amigas — recomiendo seguir a thalma para entender el tema",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@joaquin.r", "author_name": "Joaquín R.",
     "text": "La pieza de thalma sobre alquileres es de lo mejor que leí este año",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@melitam", "author_name": "Melisa M.",
     "text": "@thalma tenés que hacer una nota sobre el aumento en córdoba, te lo pido",
     "sentiment": "neutral", "intent": "question"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@fernandazz", "author_name": "Fer",
     "text": "Esto de la #leydealquileres ya no da más, estoy hace 3 meses buscando",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@nicobsas", "author_name": "Nico",
     "text": "Nadie alquila por 6 meses, todos te piden año. #alquileres",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "instagram", "kind": "post", "subject_label": "Soledad Murillo",
     "author_handle": "@solemurillo", "author_name": "Soledad Murillo",
     "text": "Ya está el nuevo episodio del pódcast — esta semana sobre el FMI",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "post", "subject_label": "Soledad Murillo",
     "author_handle": "@solemurillo", "author_name": "Soledad Murillo",
     "text": "Recorrida por Mendoza hablando con productores locales",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "post", "subject_label": "Diego Penna",
     "author_handle": "@dpenna", "author_name": "Diego Penna",
     "text": "Tres cosas que nadie te cuenta sobre la inflación esta semana",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "post", "subject_label": "Diego Penna",
     "author_handle": "@dpenna", "author_name": "Diego Penna",
     "text": "Nadie está hablando del nuevo decreto, te explico en 60s",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "facebook", "kind": "post", "subject_label": "La Trinchera (newsletter)",
     "author_handle": "latrinchera", "author_name": "La Trinchera",
     "text": "Editorial: por qué el debate de alquileres está mal planteado",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "web", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@andreaperiodista", "author_name": "Andrea L.",
     "text": "Citaron a thalma en La Nación hoy, bien merecido el reconocimiento",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@nicocba", "author_name": "Nico Córdoba",
     "text": "En Córdoba el alquiler subió 280% desde 2023 — ¿quién investiga esto?",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Política provincial",
     "author_handle": "@marisol.rosario", "author_name": "Marisol",
     "text": "Rosario está al rojo vivo y nadie le dedica una nota de fondo",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@maximinx", "author_name": "Maxi M.",
     "text": "Acabo de descubrir el newsletter de thalma y no salgo de la cama",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "facebook", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "rominam.bsas", "author_name": "Romina M.",
     "text": "Le mandé el último newsletter de thalma a mis viejos, les voló la cabeza",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "post", "subject_label": "Soledad Murillo",
     "author_handle": "@solemurillo", "author_name": "Soledad Murillo",
     "text": "Reflexión del domingo: el rol del periodismo en tiempos de polarización",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "post", "subject_label": "Diego Penna",
     "author_handle": "@dpenna", "author_name": "Diego Penna",
     "text": "Por qué la última medida del gobierno no hace lo que dice que hace",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Política provincial",
     "author_handle": "@gastoncordoba", "author_name": "Gastón",
     "text": "Otra vez nos olvidan a los del #interior, parece que solo existe el AMBA",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@isidoraok", "author_name": "Isidora",
     "text": "@thalma necesitamos una nota sobre esto urgente, te dejo el dato en DM",
     "sentiment": "neutral", "intent": "question"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@beatrizm", "author_name": "Beatriz M.",
     "text": "Me suscribí al newsletter de thalma y vale cada peso",
     "sentiment": "positive", "intent": "purchase_intent"},
    {"platform": "web", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@inmobiliariasA", "author_name": "Sector inmobiliario AR",
     "text": "Los datos sobre alquileres en redes son falsos, hay que ver el mercado real",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "facebook", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "carlosrios", "author_name": "Carlos R.",
     "text": "Le mandé a un colega la nota de thalma, dice que es excelente",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@feli23", "author_name": "Feli",
     "text": "@thalma podrías hacer un hilo en formato podcast?",
     "sentiment": "neutral", "intent": "question"},
    {"platform": "instagram", "kind": "post", "subject_label": "La Trinchera (newsletter)",
     "author_handle": "@latrinchera.news", "author_name": "La Trinchera",
     "text": "Esta semana en el newsletter: análisis del nuevo proyecto de ley",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@dieguivos", "author_name": "Diego V.",
     "text": "Acabo de rescindir el contrato, otro mes sin techo, gracias gobierno",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Política provincial",
     "author_handle": "@solrosario", "author_name": "Sol",
     "text": "Por qué nadie habla del #interior? Acá la inflación es peor #rosario",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@gimenaperiodismo", "author_name": "Gime",
     "text": "Charla con @thalma esta noche en IG live, no se lo pierdan",
     "sentiment": "positive", "intent": "other"},
    {"platform": "facebook", "kind": "post", "subject_label": "Soledad Murillo",
     "author_handle": "solemurillo", "author_name": "Soledad Murillo",
     "text": "Nueva entrevista con economista esta semana en mi canal de YT",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@andyrm", "author_name": "Andy",
     "text": "El cluster de respuestas de thalma a comentarios en IG es masterclass",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@solangem", "author_name": "Solange",
     "text": "Tres dueños se cayeron del contrato esta semana, qué pasa con los alquileres??",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "instagram", "kind": "post", "subject_label": "Diego Penna",
     "author_handle": "@diegopenna", "author_name": "Diego Penna",
     "text": "Tres claves para entender el escenario electoral 2027",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@chicaalquila", "author_name": "Anto",
     "text": "Me voy a vivir con mis viejos a los 28 #alquileresimposibles",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@elenajournal", "author_name": "Elena",
     "text": "El último newsletter de thalma me hizo pensar todo el día",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "facebook", "kind": "mention", "subject_label": "Política provincial",
     "author_handle": "andresgomez", "author_name": "Andrés G.",
     "text": "En Mendoza la cosa está difícil pero nadie del centro la cubre",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "post", "subject_label": "La Trinchera (newsletter)",
     "author_handle": "@latrinchera.news", "author_name": "La Trinchera",
     "text": "Lo que no te dijeron sobre la última conferencia del gobierno",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@martinaB", "author_name": "Martina B.",
     "text": "Hace meses que recomiendo a thalma a todo el mundo",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "post", "subject_label": "Diego Penna",
     "author_handle": "@diegopenna", "author_name": "Diego Penna",
     "text": "Mi mirada sobre las últimas declaraciones del ministro",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@laura.q", "author_name": "Laura",
     "text": "@thalma cuándo arrancás con la serie completa sobre alquileres? lo espero",
     "sentiment": "positive", "intent": "purchase_intent"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@inquilinaCABA", "author_name": "Inquilina CABA",
     "text": "El aumento del 12% mensual no es legal, no lo paguen",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "web", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@medianalisis", "author_name": "MediaAnálisis",
     "text": "Estudio: newsletters independientes como thalma crecen 40% en 2026",
     "sentiment": "positive", "intent": "other"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLASSIFICATION_KINDS = {
    "praise": "praise",
    "complaint": "complaint",
    "question": "question",
    "purchase_intent": "purchase_intent",
    "support_request": "support_request",
    "spam": "spam",
    "other": "other",
}


def random_intent_and_sentiment(mix: list[tuple[str, str]]) -> tuple[str, str]:
    return random.choice(mix)


def pick_text(intent: str, sentiment: str) -> str:
    bucket = TEMPLATES.get((intent, sentiment))
    if bucket is None:
        # Fallback to praise/positive
        bucket = TEMPLATES[("praise", "positive")]
    return random.choice(bucket)


def priority_for(intent: str, sentiment: str) -> str:
    if sentiment == "negative" and intent in ("complaint", "support_request"):
        return "high"
    if intent == "purchase_intent":
        return "high"
    if intent == "spam":
        return "low"
    return "medium"


def opportunity_for(intent: str) -> bool:
    return intent in ("purchase_intent", "praise")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

MODEL_NAME = "manual-seed"
MODEL_VERSION = "20260519"


async def main() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        tenant_id: UUID | None = await conn.fetchval(
            "SELECT id FROM tenants WHERE slug = $1", TENANT_SLUG
        )
        if tenant_id is None:
            sys.exit(
                f"tenant '{TENANT_SLUG}' not found. Run scripts/seed_dev.py first."
            )

        # Wipe everything we own for this tenant. Cascades take care of children.
        await _wipe(conn, tenant_id)

        await _insert_tracked_subjects(conn, tenant_id)
        contact_index, identity_index = await _insert_contacts(conn, tenant_id)
        await _insert_conversations_and_messages(conn, tenant_id, contact_index, identity_index)
        await _insert_mentions(conn, tenant_id)
        await _print_summary(conn, tenant_id)
    finally:
        await conn.close()


async def _wipe(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    # message_classifications, message_attachments, messages cascade from conversations
    # mention_classifications cascade from mentions
    # channel_identities cascade from contacts
    for table in (
        "mention_classifications",
        "mentions",
        "message_classifications",
        "message_attachments",
        "messages",
        "conversation_assignments",
        "conversation_notes",
        "conversations",
        "channel_identities",
        "contacts",
        "tracked_subjects",
    ):
        await conn.execute(f"DELETE FROM {table} WHERE tenant_id = $1", tenant_id)


async def _insert_tracked_subjects(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    for s in TRACKED_SUBJECTS:
        await conn.execute(
            """
            INSERT INTO tracked_subjects (
                tenant_id, kind, label, handles, keywords, hashtags, enabled
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, true)
            """,
            tenant_id,
            s["kind"],
            s["label"],
            __import__("json").dumps(s["handles"]),
            s["keywords"],
            s["hashtags"],
        )


async def _insert_contacts(
    conn: asyncpg.Connection, tenant_id: UUID
) -> tuple[list[UUID], dict[tuple[UUID, str], UUID]]:
    """Returns (contact_ids in order, {(contact_id, channel): identity_id})."""
    contact_ids: list[UUID] = []
    identity_map: dict[tuple[UUID, str], UUID] = {}
    for (ig_handle, name, fb_handle, _lean) in CONTACTS:
        contact_id = await conn.fetchval(
            """
            INSERT INTO contacts (
                tenant_id, display_name, first_seen_at, last_seen_at, profile_data
            ) VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
            """,
            tenant_id,
            name,
            NOW - timedelta(days=random.randint(5, 90)),
            NOW - timedelta(hours=random.randint(1, 240)),
            '{"source": "seed_sample"}',
        )
        contact_ids.append(contact_id)
        ig_id = await conn.fetchval(
            """
            INSERT INTO channel_identities (
                tenant_id, contact_id, channel, external_id, display_name, verified
            ) VALUES ($1, $2, 'instagram', $3, $4, false)
            RETURNING id
            """,
            tenant_id, contact_id, ig_handle, name,
        )
        identity_map[(contact_id, "instagram")] = ig_id
        if fb_handle:
            fb_id = await conn.fetchval(
                """
                INSERT INTO channel_identities (
                    tenant_id, contact_id, channel, external_id, display_name, verified
                ) VALUES ($1, $2, 'facebook', $3, $4, false)
                RETURNING id
                """,
                tenant_id, contact_id, fb_handle, name,
            )
            identity_map[(contact_id, "facebook")] = fb_id
    return contact_ids, identity_map


async def _insert_conversations_and_messages(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    contact_ids: list[UUID],
    identity_map: dict[tuple[UUID, str], UUID],
) -> None:
    msg_seq = 0
    for theme in CONVERSATION_THEMES:
        channel: str = theme["channel"]
        identity_channel = _identity_channel_for(channel)
        # Eligible contacts: those who have an identity on this channel
        eligible = [c for c in contact_ids if (c, identity_channel) in identity_map]
        if not eligible:
            continue
        n_contacts = min(theme["n_contacts"], len(eligible))
        contacts_in_thread = random.sample(eligible, n_contacts)

        msgs_per_contact = max(1, theme["n_messages"] // n_contacts)
        base_time = NOW - timedelta(days=random.randint(1, 7))

        for c_idx, contact_id in enumerate(contacts_in_thread):
            identity_id = identity_map[(contact_id, identity_channel)]
            conv_id = await conn.fetchval(
                """
                INSERT INTO conversations (
                    tenant_id, contact_id, channel, channel_identity_id,
                    external_thread_id, subject, last_message_at, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'open')
                RETURNING id
                """,
                tenant_id, contact_id, channel, identity_id,
                theme["thread_id"], theme["subject"], base_time,
            )

            # Generate messages for this contact within the thread
            n_msgs = random.randint(max(1, msgs_per_contact - 1), msgs_per_contact + 1)
            for m_idx in range(n_msgs):
                intent, sentiment = random_intent_and_sentiment(theme["default_intent_mix"])
                text = pick_text(intent, sentiment)
                sent_at = base_time + timedelta(
                    minutes=random.randint(1, 240) + c_idx * 30 + m_idx * 7
                )
                msg_seq += 1
                msg_id = await conn.fetchval(
                    """
                    INSERT INTO messages (
                        tenant_id, conversation_id, direction, sender_type,
                        content_type, content_text, external_id, sent_at, raw_payload
                    ) VALUES ($1, $2, 'inbound', 'contact', 'text', $3, $4, $5, $6::jsonb)
                    RETURNING id
                    """,
                    tenant_id, conv_id, text,
                    f"seed_{msg_seq:05d}", sent_at,
                    '{"source": "seed_sample"}',
                )
                await _insert_message_classifications(
                    conn, tenant_id, msg_id, intent, sentiment,
                )

            await conn.execute(
                "UPDATE conversations SET last_message_at = (SELECT MAX(sent_at) FROM messages WHERE conversation_id = $1) WHERE id = $1",
                conv_id,
            )


def _identity_channel_for(conv_channel: str) -> str:
    """Map conversation.channel → channel_identities.channel."""
    if conv_channel.startswith("instagram"):
        return "instagram"
    if conv_channel.startswith("facebook"):
        return "facebook"
    if conv_channel.startswith("tiktok"):
        return "tiktok"
    if conv_channel == "email":
        return "email"
    return "web"


async def _insert_message_classifications(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    message_id: UUID,
    intent: str,
    sentiment: str,
) -> None:
    rows = [
        ("sentiment", sentiment, round(random.uniform(0.75, 0.95), 3)),
        ("intent", intent, round(random.uniform(0.70, 0.95), 3)),
        ("priority", priority_for(intent, sentiment), None),
        ("opportunity", "yes" if opportunity_for(intent) else "no", None),
        ("language", "es", round(random.uniform(0.95, 0.99), 3)),
    ]
    for kind, label, confidence in rows:
        await conn.execute(
            """
            INSERT INTO message_classifications (
                tenant_id, message_id, kind, label, confidence,
                model_name, model_version, payload
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            """,
            tenant_id, message_id, kind, label, confidence,
            MODEL_NAME, MODEL_VERSION,
            '{"source": "seed_sample"}',
        )


async def _insert_mentions(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    # Map subject label → subject id
    sub_rows = await conn.fetch(
        "SELECT id, label FROM tracked_subjects WHERE tenant_id = $1",
        tenant_id,
    )
    subject_by_label = {r["label"]: r["id"] for r in sub_rows}

    for idx, m in enumerate(MENTIONS):
        sub_id = subject_by_label.get(m["subject_label"])
        published = NOW - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))
        mention_id = await conn.fetchval(
            """
            INSERT INTO mentions (
                tenant_id, tracked_subject_id, platform, kind,
                author_handle, author_display_name,
                content_text, content_url, content_published_at,
                metrics, external_id, raw_payload, apify_run_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12::jsonb, $13)
            RETURNING id
            """,
            tenant_id, sub_id, m["platform"], m["kind"],
            m["author_handle"], m["author_name"],
            m["text"], f"https://example.com/{m['platform']}/seed_{idx:03d}", published,
            __import__("json").dumps({
                "likes": random.randint(0, 1500),
                "comments_count": random.randint(0, 200),
                "shares": random.randint(0, 100),
            }),
            f"seed_mention_{idx:03d}",
            '{"source": "seed_sample"}',
            f"seed_run_{idx // 10:02d}",
        )
        # Classifications for the mention
        sentiment = m["sentiment"]
        intent = m["intent"]
        rows = [
            ("sentiment", sentiment, round(random.uniform(0.75, 0.95), 3)),
            ("intent", intent, round(random.uniform(0.70, 0.95), 3)),
            ("priority", priority_for(intent, sentiment), None),
            ("opportunity", "yes" if opportunity_for(intent) else "no", None),
            ("language", "es", round(random.uniform(0.95, 0.99), 3)),
        ]
        for kind, label, confidence in rows:
            await conn.execute(
                """
                INSERT INTO mention_classifications (
                    tenant_id, mention_id, kind, label, confidence,
                    model_name, model_version, payload
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                """,
                tenant_id, mention_id, kind, label, confidence,
                MODEL_NAME, MODEL_VERSION,
                '{"source": "seed_sample"}',
            )


async def _print_summary(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    rows = await conn.fetch(
        """
        SELECT 'tracked_subjects' AS t, COUNT(*) FROM tracked_subjects WHERE tenant_id = $1
        UNION ALL SELECT 'contacts', COUNT(*) FROM contacts WHERE tenant_id = $1
        UNION ALL SELECT 'channel_identities', COUNT(*) FROM channel_identities WHERE tenant_id = $1
        UNION ALL SELECT 'conversations', COUNT(*) FROM conversations WHERE tenant_id = $1
        UNION ALL SELECT 'messages', COUNT(*) FROM messages WHERE tenant_id = $1
        UNION ALL SELECT 'message_classifications', COUNT(*) FROM message_classifications WHERE tenant_id = $1
        UNION ALL SELECT 'mentions', COUNT(*) FROM mentions WHERE tenant_id = $1
        UNION ALL SELECT 'mention_classifications', COUNT(*) FROM mention_classifications WHERE tenant_id = $1
        """,
        tenant_id,
    )
    print(f"\nSeeded sample data for tenant '{TENANT_SLUG}':")
    for r in rows:
        print(f"  {r['t']:>26}  {r['count']:>4}")


if __name__ == "__main__":
    asyncio.run(main())
