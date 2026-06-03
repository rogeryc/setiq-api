"""Seed realistic sample data into Thalma's tenant.

Wipes and re-inserts:
  - 6 tracked_subjects (brand keywords + competitor handles)
  - ~40 contacts + their channel_identities
  - ~30 conversations across IG comments / IG DMs / FB comments /
    Messenger DMs / TikTok comments / email
  - ~120 messages with realistic Bolivian-Spanish content for a
    journalist's audience
  - message_classifications (sentiment, intent, priority, opportunity,
    language) — hand-set so dashboards have data without needing the
    Anthropic key
  - ~40 mentions (off-property posts mentioning Thalma or competitors)
  - mention_classifications

Idempotent: re-running fully resets the sample data for this tenant.
Run `scripts/seed_dev.py` first if the tenant doesn't exist yet.

Usage:
    python scripts/seed_dev_sample.py
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from setiq.auth.passwords import hash_password  # noqa: E402
from setiq.config import settings  # noqa: E402

TENANT_SLUG = "thalma"

# Deterministic randomness so re-runs produce the same data.
random.seed(42)

NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

TRACKED_SUBJECTS: list[dict[str, Any]] = [
    {
        "kind": "brand",
        "label": "Thalma (marca propia)",
        "keywords": ["thalma", "thalma news", "thalma bolivia"],
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
        "keywords": ["vivienda", "alquileres", "inquilinos", "anticrético"],
        "hashtags": ["alquileres", "vivienda"],
        "handles": {},
    },
    {
        "kind": "hashtag",
        "label": "Política departamental",
        "keywords": [],
        "hashtags": ["santacruz", "lapaz", "cochabamba", "ejetroncal"],
        "handles": {},
    },
]


# (handle_on_ig, name, fb_handle_or_none, sentiment_lean)
CONTACTS: list[tuple[str, str, str | None, str]] = [
    ("maria_fan", "María Gonzales", "maria.gonzales.sc", "positive"),
    ("nico_c_bo", "Nicolás Cabrera", None, "positive"),
    ("luchitolapaz", "Lucho B.", "lucho.b.lapaz", "neutral"),
    ("lectorsantacruz", "El Lector de Santa Cruz", None, "negative"),
    ("analiacbba", "Analía Soliz", "analia.s.cbba", "negative"),
    ("criticox", "El Crítico", None, "negative"),
    ("clara_fan_thalma", "Clara Méndez", "clara.mendez", "positive"),
    ("sofiacostas", "Sofía Costas", None, "positive"),
    ("juampi_ok", "Juan Pablo R.", "juampi.r", "neutral"),
    ("perezpaula", "Paula Pérez", None, "positive"),
    ("mateo.tarija", "Mateo (Tarija)", "mateotj", "neutral"),
    ("camilaoruro", "Camila Oruro", None, "positive"),
    ("luissucre", "Luis (Sucre)", None, "neutral"),
    ("anto.f", "Antonella F.", "antonella.f", "positive"),
    ("ferpiri", "Fer Piriz", None, "positive"),
    ("emi_santacruz", "Emi de Santa Cruz", None, "negative"),
    ("malenaq", "Malena Q.", "malena.q.bo", "negative"),
    ("nahuel_alt", "Nahuel (El Alto)", None, "neutral"),
    ("marisasc", "Marisa M.", None, "negative"),
    ("vale.cbba", "Valeria (Cochabamba)", "vale.cbba", "neutral"),
    ("rodri.cochabamba", "Rodrigo C.", None, "positive"),
    ("xime_estudia", "Ximena (estudiante)", None, "positive"),
    ("agus_v", "Agus V.", "agus.v.bo", "neutral"),
    ("flor.lapaz", "Flor B.", None, "positive"),
    ("damianp", "Damián P.", None, "negative"),
    ("luli.k", "Luli K.", "luli.k", "positive"),
    ("anonimo_42", "—", None, "negative"),  # anonymous
    ("anonimo_91", "—", None, "neutral"),
    ("tincho.b", "Martín B.", None, "neutral"),
    ("seba.r", "Sebastián R.", "seba.r.lapaz", "positive"),
    ("nadia.s", "Nadia S.", None, "positive"),
    ("nora.f", "Nora F.", "nora.f", "negative"),
    ("franky", "Francisco (Franky)", None, "neutral"),
    ("majo.escribe", "Majo P.", "majo.escribe", "positive"),
    ("juli.rio", "Julián Río", None, "neutral"),
    ("dario.mendieta", "Darío Mendieta", "dario.mendieta", "positive"),
    ("yamila_m", "Yamila M.", None, "neutral"),
    ("carla.t", "Carla T.", "carla.t.bo", "positive"),
    ("pancho.alquila", "Pancho (alquiler)", None, "negative"),
    ("ines.l", "Inés L.", "ines.l", "positive"),
]


# Templates per (intent, sentiment_lean) → list of message texts
TEMPLATES: dict[tuple[str, str], list[str]] = {
    ("praise", "positive"): [
        "Excelente nota como siempre 👏",
        "Esto es periodismo de verdad, gracias!",
        "Coincido totalmente, gracias por el trabajo",
        "Una de las mejores notas que leí este mes",
        "Gracias por meterte en este tema, hacía falta",
        "Te seguís ganando mi suscripción, una grosa",
        "Brutal el laburo de investigación, se nota cada hora",
        "Compartí esto en mi grupo, todos lo leyeron",
        "Por fin alguien que se anima a hablar del tema",
        "Necesitamos más periodismo así, fundamental",
        "Me hiciste cambiar de opinión, gracias por el laburo",
        "Pieza imprescindible, ya la mandé a 3 amigos",
        "Gracias por nombrar a la gente correcta",
        "El detalle del bloque 4 me voló la cabeza",
        "Es de las pocas notas que vale la pena leer entera",
    ],
    ("complaint", "negative"): [
        "Dejaste afuera el costo real fuera del eje troncal.",
        "Mucho centro y poca calle. La realidad acá es otra.",
        "Esa cifra no cierra, hablá con quien alquila en serio",
        "Sesgada hacia un solo lado, me decepcionó la nota",
        "Faltó la voz de quien alquila hace 5 años, no de un experto",
        "Esto es opinión disfrazada de investigación.",
        "Te falta hablar con gente de El Alto, no solo La Paz centro",
        "Datos viejos, eso ya cambió hace 6 meses",
        "Repetís lo que dice el gobierno sin chequear",
        "Te creía mejor que esto, qué decepción",
        "Ningún dato concreto, mucha generalización",
        "Sin contrastar fuentes ni una vez, ¿en serio?",
        "Generalizás de una manera que ofende a quien vive el tema",
        "Esto se publica sin chequeo editorial?",
        "El título no se corresponde con el contenido, clickbait",
    ],
    ("question", "neutral"): [
        "Cuándo publicás la siguiente parte?",
        "Tenés fuente para el dato del 38%? Me interesa citarlo",
        "Saldrá nota sobre vivienda en El Alto también?",
        "Hay versión en podcast de esta nota?",
        "Quién es la fuente del párrafo 3?",
        "Vas a hacer un seguimiento mensual del indicador?",
        "Hay algún paper académico detrás de estos números?",
        "Dónde puedo leer el informe original que citás?",
        "Tenés contacto del experto que entrevistaste?",
        "Sale versión imprimible para llevar a la reunión?",
        "Estaría bueno una versión más corta para compartir",
        "Cuándo es el próximo en vivo?",
        "Pensás hacer una nota similar pero sobre Sucre?",
        "Cuánto demora el reembolso del newsletter?",
    ],
    ("purchase_intent", "positive"): [
        "Cómo me suscribo al newsletter? Quiero pagar",
        "Pasame el link para apoyarte, me interesa",
        "Hay plan anual? Me sumo al pago",
        "Si hacés una serie completa pago entrada",
        "Aceptás pago con QR? Quiero suscribirme ya",
        "Tenés plan para empresas? Mi oficina quiere comprar 8 licencias",
        "Cuánto sale el paquete del año entero?",
        "Me sumo al pago, dónde firmo?",
        "Si abrís Patreon me sumo de una",
        "Si publicás un libro lo compro hoy mismo",
    ],
    ("support_request", "neutral"): [
        "No me llegó el último newsletter, podés revisar?",
        "El link al PDF está roto",
        "La app no me deja loguear desde ayer",
        "Cómo cambio el correo de la suscripción?",
        "Pagué pero no se actualiza mi cuenta",
        "Cómo descargo los números viejos del newsletter?",
        "Me llegó dos veces el mismo email, ¿es normal?",
        "Quiero cancelar mi suscripción, no encuentro cómo",
        "¿Reenviás un newsletter de la semana pasada?",
        "Cuál es el correo de soporte por favor",
    ],
    ("spam", "neutral"): [
        "🔥🔥🔥 visitanos en bit.ly/xxxx",
        "Gana 5.000 Bs por día desde casa - DM",
        "Hola hermosa, te escribo por DM",
        "PROMO LIMITADA - solo hoy click acá",
        "Trabajo remoto sin experiencia, 800$ semanal",
        "Inversión cripto garantizada, escribime privado",
    ],
    ("praise", "neutral"): [
        "Buena nota, interesante el ángulo",
        "Coincido con casi todo, lo voy a compartir",
        "Está bien pero esperaba un poco más",
        "El gráfico final está muy bien hecho",
        "Útil para entender el contexto general",
    ],
}


# Stock agent replies — written generically (no tenant-specific names)
# so the inbox doesn't repeat the same line over and over for the demo.
AGENT_REPLIES: list[str] = [
    "¡Gracias por escribirnos! Te respondo en un rato con detalle.",
    "Gracias por el feedback, lo paso al equipo editorial.",
    "Buen punto — vamos a hacer una nota de seguimiento.",
    "Te dejo el link a la fuente original en DM.",
    "Vamos a revisarlo y respondemos por acá hoy mismo.",
    "Estamos al tanto del tema, gracias por marcarlo.",
    "Te suscribís desde el link en la bio. ¡Bienvenida!",
    "Anotado para la próxima entrega del newsletter.",
    "Te pasamos el dato por mensaje directo.",
    "Gracias por el detalle, ya lo estamos resolviendo.",
]


# Conversation themes
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
        "subject": "Reel sobre alquileres en Santa Cruz",
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
        "thread_id": "ig_post_003_eje_troncal",
        "subject": "Comentarios sobre cobertura fuera del eje",
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
        "subject": "Comentarios FB en nota departamental",
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
     "text": "@thalma tenés que hacer una nota sobre el aumento en Cochabamba, te lo pido",
     "sentiment": "neutral", "intent": "question"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@fernandazz", "author_name": "Fer",
     "text": "Esto de los alquileres ya no da más, estoy hace 3 meses buscando en Santa Cruz",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@nicolp", "author_name": "Nico",
     "text": "Nadie alquila sin anticrético, todos te piden 10 mil dólares. #alquileres",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "instagram", "kind": "post", "subject_label": "Soledad Murillo",
     "author_handle": "@solemurillo", "author_name": "Soledad Murillo",
     "text": "Ya está el nuevo episodio del pódcast — esta semana sobre el FMI",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "post", "subject_label": "Soledad Murillo",
     "author_handle": "@solemurillo", "author_name": "Soledad Murillo",
     "text": "Recorrida por Tarija hablando con productores locales",
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
     "text": "Citaron a thalma en El Deber hoy, bien merecido el reconocimiento",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@nicococh", "author_name": "Nico Cochabamba",
     "text": "En Cochabamba el alquiler subió 80% en dos años — ¿quién investiga esto?",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Política departamental",
     "author_handle": "@marisol.santacruz", "author_name": "Marisol",
     "text": "Santa Cruz está al rojo vivo y nadie le dedica una nota de fondo",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@maximinx", "author_name": "Maxi M.",
     "text": "Acabo de descubrir el newsletter de thalma y no salgo de la cama",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "facebook", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "rominam.lpz", "author_name": "Romina M.",
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
    {"platform": "instagram", "kind": "mention", "subject_label": "Política departamental",
     "author_handle": "@gastonsucre", "author_name": "Gastón",
     "text": "Otra vez nos olvidan a los del #interior, parece que solo existe el #ejetroncal",
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
     "author_handle": "@inmobiliariasBO", "author_name": "Sector inmobiliario BO",
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
     "text": "Acabo de rescindir el contrato, otro mes sin techo en La Paz",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Política departamental",
     "author_handle": "@solsantacruz", "author_name": "Sol",
     "text": "Por qué nadie habla del #interior? Acá la inflación es peor #santacruz",
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
    {"platform": "facebook", "kind": "mention", "subject_label": "Política departamental",
     "author_handle": "andresgomez", "author_name": "Andrés G.",
     "text": "En Tarija la cosa está difícil pero nadie del centro la cubre",
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
     "author_handle": "@inquilinalapaz", "author_name": "Inquilina La Paz",
     "text": "El aumento del 12% mensual no es legal, no lo paguen",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "web", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@medianalisis", "author_name": "MediaAnálisis",
     "text": "Estudio: newsletters independientes como thalma crecen 40% en 2026",
     "sentiment": "positive", "intent": "other"},
    # Extra competitor + brand entries — gives the activity panel and
    # drill-down real density per subject for the demo.
    {"platform": "tiktok", "kind": "post", "subject_label": "Diego Penna",
     "author_handle": "@dpenna", "author_name": "Diego Penna",
     "text": "Lo que pasó esta semana con el dólar paralelo, en 90 segundos",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "post", "subject_label": "Diego Penna",
     "author_handle": "@dpenna", "author_name": "Diego Penna",
     "text": "El gobierno no quiere que sepas esto del nuevo decreto",
     "sentiment": "negative", "intent": "other"},
    {"platform": "instagram", "kind": "post", "subject_label": "Diego Penna",
     "author_handle": "@dpenna", "author_name": "Diego Penna",
     "text": "Reels: los 5 datos que no te contaron sobre el ajuste",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "post", "subject_label": "Soledad Murillo",
     "author_handle": "@solemurillo", "author_name": "Soledad Murillo",
     "text": "Nuevo episodio del podcast: ¿qué pasó con la deuda soberana?",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "post", "subject_label": "Soledad Murillo",
     "author_handle": "@solemurillo", "author_name": "Soledad Murillo",
     "text": "Hilo: cómo se reparte el presupuesto departamental este año",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "post", "subject_label": "Soledad Murillo",
     "author_handle": "@solemurillo", "author_name": "Soledad Murillo",
     "text": "El detalle del proyecto que aprobaron ayer, en 60 segundos",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "facebook", "kind": "post", "subject_label": "La Trinchera (newsletter)",
     "author_handle": "latrinchera", "author_name": "La Trinchera",
     "text": "Editorial de la semana: el rol de las redes en la polarización",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "post", "subject_label": "La Trinchera (newsletter)",
     "author_handle": "@latrinchera.news", "author_name": "La Trinchera",
     "text": "Lectura del domingo: ¿hay alternativa al modelo extractivo?",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "web", "kind": "post", "subject_label": "La Trinchera (newsletter)",
     "author_handle": "latrinchera", "author_name": "La Trinchera",
     "text": "Nuevo número: entrevista con economistas heterodoxos",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@lulaarce", "author_name": "Lula Arce",
     "text": "@thalma tu nota me hizo cancelar mi suscripción a un medio rancio",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Thalma (marca propia)",
     "author_handle": "@manudz", "author_name": "Manu",
     "text": "Le mostré la nota de thalma a mi mamá y ahora ella también la sigue",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Vivienda / alquileres",
     "author_handle": "@cristinapotosi", "author_name": "Cristina P.",
     "text": "En Potosí tampoco hay viviendas accesibles, ¿quién investiga?",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "facebook", "kind": "mention", "subject_label": "Política departamental",
     "author_handle": "luismvelasco", "author_name": "Luis Velasco",
     "text": "Tarija sigue sin recursos suficientes — ya nadie habla del tema",
     "sentiment": "negative", "intent": "complaint"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_intent_and_sentiment(mix: list[tuple[str, str]]) -> tuple[str, str]:
    return random.choice(mix)


def pick_text(intent: str, sentiment: str) -> str:
    bucket = TEMPLATES.get((intent, sentiment))
    if bucket is None:
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

        await _wipe(conn, tenant_id)
        await _insert_tracked_subjects(conn, tenant_id)
        # Team must exist before messages so outbound replies can attribute
        # to real agent users (sender_user_id).
        await _insert_team_members(conn, tenant_id)
        contact_index, identity_index = await _insert_contacts(conn, tenant_id)
        await _insert_conversations_and_messages(conn, tenant_id, contact_index, identity_index)
        await _insert_mentions(conn, tenant_id)
        await _insert_insights(conn, tenant_id)
        await _print_summary(conn, tenant_id)
    finally:
        await conn.close()


async def _wipe(conn: asyncpg.Connection, tenant_id: UUID) -> None:
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
        "insights",
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
            json.dumps(s["handles"]),
            s["keywords"],
            s["hashtags"],
        )


async def _insert_contacts(
    conn: asyncpg.Connection, tenant_id: UUID
) -> tuple[list[UUID], dict[tuple[UUID, str], UUID]]:
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
        # Half of contacts also have TikTok; one-third have email.
        if random.random() < 0.5:
            tt_id = await conn.fetchval(
                """
                INSERT INTO channel_identities (
                    tenant_id, contact_id, channel, external_id, display_name, verified
                ) VALUES ($1, $2, 'tiktok', $3, $4, false)
                RETURNING id
                """,
                tenant_id, contact_id, f"@{ig_handle}.tt", name,
            )
            identity_map[(contact_id, "tiktok")] = tt_id
        if random.random() < 0.35:
            email_handle = f"{ig_handle.replace('.', '_')}@example.com"
            em_id = await conn.fetchval(
                """
                INSERT INTO channel_identities (
                    tenant_id, contact_id, channel, external_id, display_name, verified
                ) VALUES ($1, $2, 'email', $3, $4, false)
                RETURNING id
                """,
                tenant_id, contact_id, email_handle, name,
            )
            identity_map[(contact_id, "email")] = em_id
    return contact_ids, identity_map


async def _insert_conversations_and_messages(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    contact_ids: list[UUID],
    identity_map: dict[tuple[UUID, str], UUID],
) -> None:
    # Agent user pool — for sender_user_id on outbound replies. Falls back
    # to None (allowed by schema) if the team seed didn't run for some reason.
    agent_rows = await conn.fetch(
        """
        SELECT u.id FROM users u
        JOIN tenant_users tu ON tu.user_id = u.id
        WHERE tu.tenant_id = $1 AND tu.role IN ('admin', 'agent')
          AND u.deleted_at IS NULL
        """,
        tenant_id,
    )
    agent_ids: list[UUID] = [r["id"] for r in agent_rows]

    msg_seq = 0
    for theme in CONVERSATION_THEMES:
        channel: str = theme["channel"]
        identity_channel = _identity_channel_for(channel)
        eligible = [c for c in contact_ids if (c, identity_channel) in identity_map]
        if not eligible:
            continue
        n_contacts = min(theme["n_contacts"], len(eligible))
        contacts_in_thread = random.sample(eligible, n_contacts)

        msgs_per_contact = max(1, theme["n_messages"] // n_contacts)
        # Bias toward recent so the 7-day TMR window has data, while
        # keeping some > 30 days for the "vs mes anterior" delta.
        bucket = random.random()
        if bucket < 0.5:
            days_back = random.randint(1, 10)   # active week, half the themes
        elif bucket < 0.8:
            days_back = random.randint(11, 30)
        else:
            days_back = random.randint(31, 60)  # prior-period coverage
        base_time = NOW - timedelta(days=days_back)

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
                    conn, tenant_id, msg_id, intent, sentiment, sent_at,
                )

                # ~60% chance an agent replies 5-90 minutes later. Skip when
                # the intent is spam — wouldn't get a human reply.
                if intent != "spam" and agent_ids and random.random() < 0.6:
                    reply_at = sent_at + timedelta(minutes=random.randint(5, 90))
                    if reply_at <= NOW:
                        msg_seq += 1
                        await conn.execute(
                            """
                            INSERT INTO messages (
                                tenant_id, conversation_id, direction, sender_type,
                                sender_user_id, content_type, content_text,
                                external_id, sent_at, raw_payload
                            ) VALUES ($1, $2, 'outbound', 'agent', $3, 'text',
                                      $4, $5, $6, $7::jsonb)
                            """,
                            tenant_id, conv_id, random.choice(agent_ids),
                            random.choice(AGENT_REPLIES),
                            f"seed_{msg_seq:05d}", reply_at,
                            '{"source": "seed_sample"}',
                        )

            await conn.execute(
                "UPDATE conversations SET last_message_at = (SELECT MAX(sent_at) FROM messages WHERE conversation_id = $1) WHERE id = $1",
                conv_id,
            )


def _identity_channel_for(conv_channel: str) -> str:
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
    sent_at: datetime | None = None,
) -> None:
    """Insert one row per (message, kind). `created_at` is set to a moment
    slightly after the message's sent_at so the sparkline + period-over-period
    queries see realistic timestamps."""
    classified_at = sent_at + timedelta(seconds=random.randint(2, 30)) if sent_at else NOW
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
                model_name, model_version, payload, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
            """,
            tenant_id, message_id, kind, label, confidence,
            MODEL_NAME, MODEL_VERSION,
            '{"source": "seed_sample"}',
            classified_at,
        )


async def _insert_mentions(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    sub_rows = await conn.fetch(
        "SELECT id, label FROM tracked_subjects WHERE tenant_id = $1",
        tenant_id,
    )
    subject_by_label = {r["label"]: r["id"] for r in sub_rows}

    for idx, m in enumerate(MENTIONS):
        sub_id = subject_by_label.get(m["subject_label"])
        # ~60% in the last 7 days, ~30% in the prior week, ~10% older.
        # Gives the competitor activity panel + drill-down real data to show
        # for a 7-day window, plus enough history for the WoW delta to vary.
        bucket = random.random()
        if bucket < 0.6:
            days_ago = random.randint(0, 6)
        elif bucket < 0.9:
            days_ago = random.randint(7, 13)
        else:
            days_ago = random.randint(14, 30)
        published = NOW - timedelta(days=days_ago, hours=random.randint(0, 23))
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
            json.dumps({
                "likes": random.randint(0, 1500),
                "comments_count": random.randint(0, 200),
                "shares": random.randint(0, 100),
            }),
            f"seed_mention_{idx:03d}",
            '{"source": "seed_sample"}',
            f"seed_run_{idx // 10:02d}",
        )
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


INSIGHTS_SEED: list[dict[str, Any]] = [
    {
        "kind": "lead",
        "rank": 0,
        "title": "Thalma está siendo escuchada.",
        "title_em": "Y empezando a pedir cosas.",
        "body": (
            "Sentimiento estable salvo después de la nota del lunes en Santa Cruz, "
            "donde un sector concentró críticas. La audiencia de TikTok empuja una "
            "serie sobre vivienda — la oportunidad tiene 3 meses."
        ),
        "actions": [],
    },
    {
        "kind": "featured",
        "rank": 0,
        "title": "La nota sobre vivienda está disparando",
        "title_em": "57 comentarios negativos",
        "title_tail": "en 72h.",
        "body": (
            "Las críticas se concentran en lectoras de Santa Cruz y Cochabamba que "
            "sienten que dejaste fuera el costo fuera del eje troncal. Sentimiento "
            "general aún positivo (0,72), pero el cluster geográfico es contenible "
            "si respondés con una nota lateral esta semana."
        ),
        "confidence": "92%",
        "age": "hace 1h",
        "impact": "Impacto: corte de viralización en Twitter / Threads",
        "actions": [
            {"label": "Abrir hilo · Pasar a borrador", "route": "/inbox", "variant": "acc"},
            {"label": "Asignar a Sole", "variant": "ghost"},
        ],
    },
    {
        "kind": "memo",
        "rank": 1,
        "severity": "med",
        "tag": "Memo 02 · Oportunidad",
        "confidence": "Confianza 81%",
        "title": "Audiencia 18-24 pidiendo",
        "title_em": "serie sobre alquileres",
        "body": (
            "Detectamos 87 menciones espontáneas en TikTok pidiendo una serie sobre "
            "alquileres y subarriendos, concentradas en mujeres 18-24. Sugerimos "
            "probar un primer episodio antes de comprometer una serie completa."
        ),
        "footnote": "Potencial: 12-18%",
        "actions": [{"label": "Crear segmento", "variant": "acc"}],
    },
    {
        "kind": "memo",
        "rank": 2,
        "severity": "med",
        "tag": "Memo 03 · Audiencia",
        "confidence": "Confianza 88%",
        "title": "Cluster emergente: 184 lectoras-promotoras orgánicas",
        "body": (
            "Identificamos un cluster de 184 cuentas con sentimiento sostenido sobre "
            "0,9 en los últimos 60 días, sin ningún programa formal. Recomendamos "
            "formalizar contacto antes que otros newsletters las capten."
        ),
        "footnote": "Base embajadoras",
        "actions": [{"label": "Exportar segmento"}],
    },
    {
        "kind": "memo",
        "rank": 3,
        "severity": "low",
        "tag": "Memo 04 · Operación",
        "confidence": "Confianza 74%",
        "title": "TMR domingos en 1h 42min",
        "body": (
            "El tiempo medio de primera respuesta los domingos supera el SLA en 3,4×. "
            "Recomendamos reasignar un agente del lunes al domingo durante los próximos "
            "4 fines de semana para evaluar impacto."
        ),
        "footnote": "SLA en 4 semanas",
        "actions": [{"label": "Ver calendario"}],
    },
    # --- Más insights para el feed de Recomendaciones ---
    {
        "kind": "featured",
        "rank": 1,
        "title": "El Reel del jueves disparó",
        "title_em": "230 nuevas seguidoras",
        "title_tail": "en 36h.",
        "body": (
            "El video sobre alquileres en Cochabamba captó audiencia 25-34 que no "
            "estaba en tu base habitual. Sugerimos serializar el formato — el "
            "engagement rate (12,4%) está 3,2× sobre tu promedio."
        ),
        "confidence": "89%",
        "age": "hace 6h",
        "impact": "Impacto: expansión a un nuevo segmento etario",
        "actions": [
            {"label": "Crear segmento 25-34", "variant": "acc"},
            {"label": "Ver Reel"},
        ],
    },
    {
        "kind": "featured",
        "rank": 2,
        "title": "La Trinchera publicó una pieza",
        "title_em": "que solapa con tu serie",
        "title_tail": "de alquileres.",
        "body": (
            "El newsletter La Trinchera sacó hoy una nota sobre el mismo tema. "
            "Su ángulo es más político; el tuyo tiene más data de campo. Vale la "
            "pena marcar la diferencia antes que tu audiencia los mezcle."
        ),
        "confidence": "85%",
        "age": "hace 2h",
        "impact": "Impacto: diferenciación editorial",
        "actions": [
            {"label": "Ver nota de La Trinchera"},
            {"label": "Crear respuesta editorial", "variant": "ghost"},
        ],
    },
    {
        "kind": "memo",
        "rank": 4,
        "severity": "low",
        "tag": "Memo 05 · Audiencia",
        "confidence": "Confianza 78%",
        "title": "Pico de actividad",
        "title_em": "martes 21h",
        "body": (
            "Tu audiencia se activa en IG entre 20:30 y 22:00 los martes "
            "consistentemente. Hoy publicás cuando estás disponible — alinear el "
            "calendario con ese pico puede subir el alcance ~18%."
        ),
        "footnote": "+18% alcance estimado",
        "actions": [{"label": "Ajustar calendario"}],
    },
    {
        "kind": "memo",
        "rank": 5,
        "severity": "med",
        "tag": "Memo 06 · Oportunidad",
        "confidence": "Confianza 83%",
        "title": "Darío Mendieta te mencionó",
        "title_em": "4 veces este mes",
        "body": (
            "Periodista de Sucre con 12k seguidoras, sentimiento sostenido 0,92 "
            "hacia tu trabajo. Buen candidato para una colab o entrevista "
            "cruzada."
        ),
        "footnote": "Colab potencial",
        "actions": [{"label": "Ver perfil"}],
    },
    {
        "kind": "memo",
        "rank": 6,
        "severity": "high",
        "tag": "Memo 07 · Servicio",
        "confidence": "Confianza 91%",
        "title": "3 suscriptores reportan",
        "title_em": "newsletter no llega",
        "body": (
            "Tres correos distintos (todos en dominios Yahoo) marcaron como spam "
            "los últimos 2 envíos. Conviene revisar SPF/DKIM antes del próximo "
            "ciclo del miércoles."
        ),
        "footnote": "Bloqueo deliverability",
        "actions": [{"label": "Revisar configuración email", "variant": "acc"}],
    },
    {
        "kind": "memo",
        "rank": 7,
        "severity": "low",
        "tag": "Memo 08 · Audiencia",
        "confidence": "Confianza 71%",
        "title": "Sentimiento en Santa Cruz",
        "title_em": "subió 8 pp",
        "body": (
            "Las últimas 3 piezas con foco en el oriente movieron el sentimiento "
            "de Santa Cruz de 0,58 a 0,66. Cobertura del eje troncal está "
            "rindiendo."
        ),
        "footnote": "Métrica regional",
        "actions": [{"label": "Ver detalle por ciudad"}],
    },
    {
        "kind": "memo",
        "rank": 8,
        "severity": "med",
        "tag": "Memo 09 · Operación",
        "confidence": "Confianza 80%",
        "title": "12 menciones sin responder",
        "title_em": "esperan más de 48h",
        "body": (
            "Hay 12 conversaciones con sentimiento neutral o positivo donde la "
            "primera respuesta supera el SLA. Bajo riesgo individual pero "
            "patrón a corregir."
        ),
        "footnote": "Backlog inbox",
        "actions": [{"label": "Ir al inbox", "route": "/inbox"}],
    },
    {
        "kind": "memo",
        "rank": 9,
        "severity": "low",
        "tag": "Memo 10 · Audiencia",
        "confidence": "Confianza 68%",
        "title": "Cluster emergente:",
        "title_em": "estudiantes de periodismo",
        "body": (
            "Detectamos ~30 cuentas que se identifican como estudiantes de "
            "periodismo siguiendo a Thalma + 2-3 competidores. Audiencia útil "
            "para un newsletter educativo paralelo."
        ),
        "footnote": "Idea: serie 'cómo cubrir X'",
        "actions": [{"label": "Crear segmento"}],
    },
    {
        "kind": "memo",
        "rank": 10,
        "severity": "med",
        "tag": "Memo 11 · Competencia",
        "confidence": "Confianza 79%",
        "title": "Diego Penna está acelerando",
        "title_em": "+52% en menciones",
        "body": (
            "El competidor con mayor crecimiento esta semana es Diego Penna. "
            "Su línea editorial en TikTok se solapa con la tuya en alquileres "
            "y dólar paralelo. Vale la pena revisar qué formatos están funcionando."
        ),
        "footnote": "Mirar /segmentos para detalle.",
        "actions": [{"label": "Abrir competidor", "route": "/segmentos"}],
    },
    {
        "kind": "memo",
        "rank": 11,
        "severity": "high",
        "tag": "Memo 12 · Crisis temprana",
        "confidence": "Confianza 87%",
        "title": "Pico de quejas con",
        "title_em": "tono coordinado",
        "body": (
            "12 comentarios negativos en 4 horas usando frases muy similares en "
            "la nota de Santa Cruz — patrón compatible con una campaña organizada. "
            "Aún no escaló a Twitter. Si respondés en las próximas 6h, la "
            "probabilidad de que muera ahí es ~70%."
        ),
        "footnote": "Ver hilo completo en /inbox.",
        "actions": [{"label": "Abrir hilo", "route": "/inbox", "variant": "acc"}],
    },
    {
        "kind": "memo",
        "rank": 12,
        "severity": "low",
        "tag": "Memo 13 · Performance",
        "confidence": "Confianza 74%",
        "title": "Mejor horario de respuesta:",
        "title_em": "18:00-21:00 La Paz",
        "body": (
            "Cuando respondés DMs en ese rango, la tasa de conversación que "
            "termina en suscripción es 2.4× más alta que el resto del día. "
            "Sugerencia: bloquear una ventana fija para esto."
        ),
        "footnote": "Métrica calculada sobre últimos 30 días.",
        "actions": [],
    },
    {
        "kind": "memo",
        "rank": 13,
        "severity": "med",
        "tag": "Memo 14 · Oportunidad",
        "confidence": "Confianza 83%",
        "title": "Hilo viral en X menciona",
        "title_em": "a Thalma como referencia",
        "body": (
            "Un hilo de 1.2k retuits sobre alquileres en El Alto cita la nota "
            "tuya del mes pasado como fuente. 38 cuentas nuevas siguieron en "
            "las primeras 6 horas. Probable bump sostenido si publicás algo "
            "complementario esta semana."
        ),
        "footnote": "Considerar una nota corta de seguimiento.",
        "actions": [{"label": "Crear borrador", "variant": "ghost"}],
    },
    {
        "kind": "memo",
        "rank": 14,
        "severity": "low",
        "tag": "Memo 15 · Inbox health",
        "confidence": "Confianza 91%",
        "title": "Tiempo medio de respuesta",
        "title_em": "subió a 4h 12m",
        "body": (
            "Hace 30 días estabas en 2h 50m. La mitad del aumento viene de "
            "conversaciones de DM que esperan tu respuesta personal. "
            "Plantillas de soporte cubrirían 6 de los 10 tipos más frecuentes."
        ),
        "footnote": "Detalle: KPI 'TMR · Kaizen' en /overview.",
        "actions": [{"label": "Ver inbox", "route": "/inbox"}],
    },
]


async def _insert_insights(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    for s in INSIGHTS_SEED:
        await conn.execute(
            """
            INSERT INTO insights (
                tenant_id, kind, severity, tag, title, title_em, title_tail,
                body, confidence, age, impact, footnote, actions, rank, enabled
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                $8, $9, $10, $11, $12, $13::jsonb, $14, true
            )
            """,
            tenant_id,
            s["kind"],
            s.get("severity"),
            s.get("tag"),
            s["title"],
            s.get("title_em"),
            s.get("title_tail"),
            s["body"],
            s.get("confidence"),
            s.get("age"),
            s.get("impact"),
            s.get("footnote"),
            json.dumps(s.get("actions", [])),
            s.get("rank", 0),
        )


# (email, name, role, password, days_since_last_login)
TEAM_SEED: list[tuple[str, str, str, str, int]] = [
    ("saul@example.com", "Saúl Vargas",  "admin", "changeme123", 1),
    ("sole@example.com", "Sole Quiroga", "agent", "changeme123", 0),
    ("eli@example.com",  "Eli Rojas",    "agent", "changeme123", 4),
    ("ana@example.com",  "Ana Aramayo",  "viewer", "changeme123", 12),
]


async def _insert_team_members(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    """Add a few extra users (besides Thalma) so the Equipo page has volume.

    Idempotent: re-running upserts users by email and re-links them to the
    tenant. We DO NOT touch the existing thalma user/role.
    """
    for (email, name, role, password, days_ago) in TEAM_SEED:
        user_id = await conn.fetchval(
            """
            INSERT INTO users (email, password_hash, name, last_login_at)
            VALUES ($1, $2, $3, NOW() - ($4 || ' days')::interval)
            ON CONFLICT (email) DO UPDATE SET
                name = EXCLUDED.name,
                last_login_at = EXCLUDED.last_login_at
            RETURNING id
            """,
            email, hash_password(password), name, str(days_ago),
        )
        await conn.execute(
            """
            INSERT INTO tenant_users (tenant_id, user_id, role)
            VALUES ($1, $2, $3)
            ON CONFLICT (tenant_id, user_id) DO UPDATE SET role = EXCLUDED.role
            """,
            tenant_id, user_id, role,
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
        UNION ALL SELECT 'insights', COUNT(*) FROM insights WHERE tenant_id = $1
        """,
        tenant_id,
    )
    print(f"\nSeeded sample data for tenant '{TENANT_SLUG}':")
    for r in rows:
        print(f"  {r['t']:>26}  {r['count']:>4}")


if __name__ == "__main__":
    asyncio.run(main())
