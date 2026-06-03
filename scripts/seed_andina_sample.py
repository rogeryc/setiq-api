"""Seed the second demo tenant — Cervecería Andina.

Industry: consumer goods (beverages).
Purpose: cross-industry demo + multi-tenant testing.

Creates the tenant if missing, wipes its existing demo data, and reseeds:
  - tracked subjects (1 brand + 4 competitors + 2 topics + 2 hashtags)
  - ~45 contacts with beverage-consumer handles
  - 10 conversation themes industry-specific (lote complaints, distribution,
    fiesta engagement, fútbol partnership, etc.)
  - ~65 off-property mentions across brand + competitors, biased to recent
  - 12 insights (lead/featured/memos) tuned for consumer-goods voice
  - admin user demo@andina.example.com / changeme123
  - thalma@example.com is added as Admin so the masthead tenant switcher has
    both tenants to flip between

Usage:
    uv run python scripts/seed_andina_sample.py

Idempotent: re-running drops the tenant's seeded rows and reinserts.
"""
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

TENANT_SLUG = "andina"
TENANT_NAME = "Cervecería Andina"
ADMIN_EMAIL = "demo@andina.example.com"

NOW = datetime.now(UTC)
MODEL_NAME = "claude-3-5-sonnet"
MODEL_VERSION = "20260519"
random.seed(42)


# ---------------------------------------------------------------------------
# Reusable bits (kept inline so the script is self-contained)
# ---------------------------------------------------------------------------

def priority_for(intent: str, sentiment: str) -> str:
    if intent == "complaint" and sentiment == "negative":
        return "high"
    if intent in ("purchase_intent", "support_request"):
        return "medium"
    return "low"


def opportunity_for(intent: str) -> bool:
    return intent in ("purchase_intent", "praise")


def random_intent_and_sentiment(mix: list[tuple[str, str]]) -> tuple[str, str]:
    return random.choice(mix)


def pick_text(intent: str, sentiment: str) -> str:
    key = (intent, sentiment)
    pool = TEMPLATES.get(key) or TEMPLATES.get((intent, "neutral")) or ["..."]
    return random.choice(pool)


# ---------------------------------------------------------------------------
# Industry-specific seed content
# ---------------------------------------------------------------------------

TRACKED_SUBJECTS: list[dict[str, Any]] = [
    {
        "kind": "brand",
        "label": "Andina (marca propia)",
        "handles": {
            "instagram": "@cerveceriaandina",
            "facebook": "Cervecería Andina",
            "tiktok": "@andina.beer",
        },
        "keywords": ["andina", "andina pilsen", "cerveza andina"],
        "hashtags": ["andinaes", "cervezaandina"],
    },
    {
        "kind": "competitor",
        "label": "Heineken",
        "handles": {"instagram": "@heineken_bo", "facebook": "Heineken Bolivia"},
        "keywords": ["heineken"],
        "hashtags": [],
    },
    {
        "kind": "competitor",
        "label": "Corona",
        "handles": {"instagram": "@corona_bo", "facebook": "Corona Bolivia"},
        "keywords": ["corona", "coronita"],
        "hashtags": [],
    },
    {
        "kind": "competitor",
        "label": "Stella Artois",
        "handles": {"instagram": "@stellaartois_bo"},
        "keywords": ["stella", "stella artois"],
        "hashtags": [],
    },
    {
        "kind": "competitor",
        "label": "Cerveza del Valle",
        "handles": {"instagram": "@cervezadelvalle", "tiktok": "@delvalle.bo"},
        "keywords": ["cerveza del valle", "del valle"],
        "hashtags": [],
    },
    {
        "kind": "keyword",
        "label": "Cerveza artesanal",
        "handles": {},
        "keywords": ["cerveza artesanal", "artesanal", "craft beer"],
        "hashtags": [],
    },
    {
        "kind": "keyword",
        "label": "Fiesta y eventos",
        "handles": {},
        "keywords": ["fiesta", "carnaval", "fin de año", "evento"],
        "hashtags": [],
    },
    {
        "kind": "hashtag",
        "label": "#cervezaboliviana",
        "handles": {},
        "keywords": [],
        "hashtags": ["cervezaboliviana"],
    },
    {
        "kind": "hashtag",
        "label": "#sedfría",
        "handles": {},
        "keywords": [],
        "hashtags": ["sedfría", "sedfria"],
    },
]


# Consumer-style names + handles; bilingual mix typical for BO youth audience
CONTACTS: list[dict[str, Any]] = [
    {"name": "Mateo Aguilar",    "handles": {"instagram": "@mateoag"}},
    {"name": "Camila Suárez",    "handles": {"instagram": "@camisuarez", "facebook": "Camila Suárez"}},
    {"name": "Luciano R.",       "handles": {"instagram": "@luchi.r"}},
    {"name": "Florencia O.",     "handles": {"instagram": "@floor.o", "tiktok": "@floor.oo"}},
    {"name": "Nico Villarroel",  "handles": {"facebook": "Nico Villarroel"}},
    {"name": "Sebastián Loza",   "handles": {"instagram": "@sebaloza"}},
    {"name": "Andrea Quispe",    "handles": {"tiktok": "@andreqq"}},
    {"name": "Joaquín M.",       "handles": {"instagram": "@joaquinm.bo", "email": "joaquin.m@gmail.com"}},
    {"name": "Daniela P.",       "handles": {"instagram": "@danip.cocha"}},
    {"name": "Ignacio Vargas",   "handles": {"instagram": "@ignaciov"}},
    {"name": "Sofía Méndez",     "handles": {"facebook": "Sofía Méndez", "instagram": "@sofime"}},
    {"name": "Renato C.",        "handles": {"tiktok": "@renato.cb"}},
    {"name": "Valeria Z.",       "handles": {"instagram": "@vale_zz"}},
    {"name": "Diego Aparicio",   "handles": {"facebook": "Diego Aparicio"}},
    {"name": "Camilo Velasco",   "handles": {"instagram": "@camilovel"}},
    {"name": "Romina G.",        "handles": {"tiktok": "@rominag"}},
    {"name": "Bruno Z.",         "handles": {"instagram": "@brunozz"}},
    {"name": "Antonella P.",     "handles": {"instagram": "@antop"}},
    {"name": "Fernando R.",      "handles": {"facebook": "Fernando R.", "email": "fer.r@gmail.com"}},
    {"name": "Lucía M.",         "handles": {"instagram": "@lucim.bo"}},
    {"name": "Tomás L.",         "handles": {"tiktok": "@tomasl"}},
    {"name": "Paula Ríos",       "handles": {"instagram": "@paularios"}},
    {"name": "Joaquín Z.",       "handles": {"facebook": "Joaquín Z."}},
    {"name": "Belén C.",         "handles": {"instagram": "@belenccr"}},
    {"name": "Marcos T.",        "handles": {"facebook": "Marcos T."}},
    {"name": "Agustina V.",      "handles": {"tiktok": "@agusvv"}},
    {"name": "Esteban G.",       "handles": {"instagram": "@estebagg"}},
    {"name": "Carola B.",        "handles": {"instagram": "@carolabb", "email": "carola.b@gmail.com"}},
    {"name": "Jorge Aramayo",    "handles": {"facebook": "Jorge Aramayo"}},
    {"name": "Natalia P.",       "handles": {"instagram": "@natipp"}},
    {"name": "Distribuidora Sur","handles": {"email": "ventas@distribsur.bo"}},
    {"name": "Almacenes Norte",  "handles": {"email": "compras@almacenesnorte.bo"}},
    {"name": "Bar La Plaza",     "handles": {"instagram": "@bar.laplaza", "email": "contacto@barlaplaza.bo"}},
    {"name": "Resto El Patio",   "handles": {"instagram": "@elpatio.santacruz"}},
    {"name": "Eventos Cochabamba","handles": {"email": "info@eventoscbba.bo"}},
    {"name": "Federico K.",      "handles": {"instagram": "@fedek"}},
    {"name": "Carla Z.",         "handles": {"instagram": "@carlaz"}},
    {"name": "Lautaro R.",       "handles": {"tiktok": "@lautar"}},
    {"name": "Micaela O.",       "handles": {"instagram": "@micaelao"}},
    {"name": "Hernán T.",        "handles": {"facebook": "Hernán T."}},
    {"name": "Sole G.",          "handles": {"instagram": "@soleg"}},
    {"name": "Joel V.",          "handles": {"tiktok": "@joelv"}},
    {"name": "Constanza V.",     "handles": {"instagram": "@constav"}},
    {"name": "Bruno Méndez",     "handles": {"facebook": "Bruno Méndez"}},
    {"name": "Mateo F.",         "handles": {"instagram": "@mateof"}},
]


TEMPLATES: dict[tuple[str, str], list[str]] = {
    ("praise", "positive"): [
        "Esta cerveza es la mejor para una asado, gracias por mantener calidad 🍻",
        "Probé la nueva edición limitada y está brutal",
        "Mejor cerveza nacional, sin discusión",
        "La pilsen helada con el viernes 30°C, no hay mejor combo",
        "El último envase nuevo está genial, mucho más cómodo",
        "Compré 2 cajas para la fiesta y se acabaron en 2 horas, todos preguntaban qué cerveza era",
        "Gracias por el patrocinio de la peña del barrio, gran gesto",
        "La calidad sigue siendo top, generación tras generación",
        "Llegué a casa cansado y abrir una Andina helada me arregló el día",
        "Felicitaciones por la campaña, súper bien hecha y muy boliviana",
    ],
    ("complaint", "negative"): [
        "El lote A-2389 sabe distinto, parece pasado",
        "Compré 6 unidades y 2 venían sin gas, qué pasa con el QC?",
        "El precio subió 15% sin aviso, no se justifica",
        "La promo del fin de semana no llegó al interior, otra vez ignoran al sur",
        "El envase nuevo se cae fácil del soporte, problema de diseño",
        "Esa publicidad con el partido fue ofensiva, gente quejándose en Twitter",
        "Pedí distribución en Tarija y nadie responde hace 3 semanas",
        "El sabor cambió, ya no es lo de antes",
        "Recibí una caja con 3 botellas rotas, nadie me contesta el reclamo",
        "El precio en supermercado es 20% más alto que en almacén, donde controlan eso?",
        "Pusieron precio diferenciado por región sin avisar, hay quejas en grupos de FB",
        "Lote vencido en almacenes barriales, control de cadena fallando",
    ],
    ("question", "neutral"): [
        "Cuándo lanzan la edición limitada de carnaval?",
        "Hay distribución en Sucre? No la encuentro hace meses",
        "Tienen versión sin alcohol? Quiero probar pero estoy de tratamiento",
        "Cuál es el promedio de calorías por lata? Necesito el dato",
        "Cuándo vuelven a hacer la promo del 2x1?",
        "El sponsor del Tigre sigue para esta temporada?",
        "Hay tour por la planta? Mi novio es fanático",
        "Dónde compro al por mayor para un evento de 80 personas?",
        "Tienen merchandising oficial? Quiero comprar polos",
        "La nueva variante es para todo el año o sólo edición especial?",
    ],
    ("purchase_intent", "positive"): [
        "Necesito 5 cajas para una fiesta el sábado, dónde compro?",
        "Mi bar quiere venderla, cómo abro cuenta como distribuidor?",
        "Hay paquete corporativo? Tengo evento de 200 personas",
        "Quiero patrocinar con su cerveza un evento universitario, contacto?",
        "Estoy abriendo un resto y los quiero como proveedor exclusivo",
        "Necesito 3 chops + 10 cajas para la inauguración del local",
        "Compré varias para regalar en fin de año, hay descuento por volumen?",
    ],
    ("support_request", "neutral"): [
        "Me llegó una caja con 4 latas chuecas, dónde reclamo?",
        "El código del concurso no me funciona en la web",
        "No me llegó el merch que gané en el sorteo del IG",
        "La gift card no se canjeó, podés revisar el código X-220?",
        "Quiero cambiar el correo registrado en el programa de puntos",
        "El delivery vino con 2 latas reventadas, cómo procedo?",
    ],
    ("spam", "neutral"): [
        "🔥🔥🔥 promo única descuento 80% click acá",
        "GANA 5000 Bs - registrate antes que termine",
        "Trabajo remoto desde casa, escribime privado",
    ],
    ("praise", "neutral"): [
        "Buena cerveza, no me decepciona",
        "Para el verano siempre vuelvo a la Andina",
        "Coincido con casi todos los comentarios positivos",
    ],
}


AGENT_REPLIES: list[str] = [
    "¡Gracias por escribirnos! Te respondemos en un rato con detalle.",
    "Recibimos tu reclamo, lo pasamos a calidad. Vuelven con vos hoy.",
    "Gracias por el feedback, lo compartimos con el equipo de marketing.",
    "Te dejo el link a nuestro programa de distribuidores en DM.",
    "Sí, hay versión sin alcohol — te pasamos los puntos de venta.",
    "Estamos al tanto del problema, lo revisamos con producción.",
    "Para volumen mayor a 50 cajas hay tarifa especial — te llamamos hoy.",
    "Gracias por la felicitación, se la pasamos al equipo de la planta.",
    "Anotado para la próxima edición del newsletter de eventos.",
    "Te enviamos al equipo de soporte para resolver el reclamo del lote.",
]


CONVERSATION_THEMES: list[dict[str, Any]] = [
    {
        "channel": "instagram_comment",
        "thread_id": "ig_post_andina_lanzamiento",
        "subject": "Comentarios — lanzamiento edición Carnaval",
        "default_intent_mix": [("praise", "positive"), ("question", "neutral"), ("purchase_intent", "positive")],
        "n_contacts": 9, "n_messages": 22,
    },
    {
        "channel": "instagram_comment",
        "thread_id": "ig_post_lote_a2389",
        "subject": "Comentarios — quejas por lote A-2389",
        "default_intent_mix": [("complaint", "negative"), ("question", "neutral"), ("complaint", "negative")],
        "n_contacts": 6, "n_messages": 14,
    },
    {
        "channel": "instagram_dm",
        "thread_id": None,
        "subject": "DMs — pedidos de distribución y compra al por mayor",
        "default_intent_mix": [("purchase_intent", "positive"), ("question", "neutral")],
        "n_contacts": 5, "n_messages": 12,
    },
    {
        "channel": "facebook_comment",
        "thread_id": "fb_post_sponsor_tigre",
        "subject": "Comentarios — patrocinio fútbol",
        "default_intent_mix": [("praise", "positive"), ("complaint", "negative"), ("question", "neutral")],
        "n_contacts": 7, "n_messages": 16,
    },
    {
        "channel": "facebook_dm",
        "thread_id": None,
        "subject": "Messenger — reclamos calidad",
        "default_intent_mix": [("complaint", "negative"), ("support_request", "neutral")],
        "n_contacts": 4, "n_messages": 10,
    },
    {
        "channel": "tiktok_comment",
        "thread_id": "tt_video_verano",
        "subject": "TikTok — campaña de verano",
        "default_intent_mix": [("praise", "positive"), ("praise", "positive"), ("question", "neutral")],
        "n_contacts": 8, "n_messages": 18,
    },
    {
        "channel": "tiktok_comment",
        "thread_id": "tt_video_artesanal",
        "subject": "TikTok — comparación con cerveza artesanal",
        "default_intent_mix": [("praise", "neutral"), ("complaint", "negative"), ("question", "neutral")],
        "n_contacts": 5, "n_messages": 11,
    },
    {
        "channel": "email",
        "thread_id": "email_corporativo_2026",
        "subject": "Email — clientes corporativos / B2B",
        "default_intent_mix": [("purchase_intent", "positive"), ("support_request", "neutral")],
        "n_contacts": 4, "n_messages": 9,
    },
    {
        "channel": "instagram_comment",
        "thread_id": "ig_post_envase_nuevo",
        "subject": "Comentarios — envase nuevo (críticas + felicitaciones)",
        "default_intent_mix": [("complaint", "negative"), ("praise", "positive"), ("question", "neutral")],
        "n_contacts": 6, "n_messages": 14,
    },
    {
        "channel": "facebook_comment",
        "thread_id": "fb_post_precio",
        "subject": "Comentarios — críticas por suba de precio",
        "default_intent_mix": [("complaint", "negative"), ("complaint", "negative"), ("question", "neutral")],
        "n_contacts": 5, "n_messages": 12,
    },
]


MENTIONS: list[dict[str, Any]] = [
    {"platform": "instagram", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@brunozz", "author_name": "Bruno Z.",
     "text": "@cerveceriaandina patrocinen el cumple del barrio y todos felices",
     "sentiment": "positive", "intent": "purchase_intent"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@floor.o", "author_name": "Florencia O.",
     "text": "Sigo siendo team Andina, no hay con qué darle en verano",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@joelv", "author_name": "Joel V.",
     "text": "Probando la edición Carnaval — sabe a recuerdos de la infancia",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "facebook", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "fernandor.lpz", "author_name": "Fernando R.",
     "text": "Compré una caja para el asado del sábado, todos pidieron repetir",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@danip.cocha", "author_name": "Dani P.",
     "text": "Si tienen distribución acá en Cocha por favor que me avisen, no encuentro",
     "sentiment": "neutral", "intent": "question"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@lautar", "author_name": "Lautaro R.",
     "text": "La Andina es básica pero está bien, ni mala ni excelente, está ok",
     "sentiment": "neutral", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@carolabb", "author_name": "Carola B.",
     "text": "Mi padre toma Andina hace 30 años, ya es parte de la familia",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@belenccr", "author_name": "Belén C.",
     "text": "@cerveceriaandina por favor traigan la edición de fiesta a Sucre",
     "sentiment": "neutral", "intent": "question"},
    {"platform": "facebook", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "hernantatchel", "author_name": "Hernán T.",
     "text": "El nuevo envase no es práctico para el cooler, vuelvan al diseño viejo",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@joaquinm.bo", "author_name": "Joaquín M.",
     "text": "Probé la pilsen sin alcohol y está sorprendentemente buena",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@vale_zz", "author_name": "Vale Z.",
     "text": "El último lote del IG me dio dolor de cabeza, raro la verdad",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Andina (marca propia)",
     "author_handle": "@constav", "author_name": "Constanza V.",
     "text": "La campaña con jóvenes está bien lograda, me gusta el ángulo",
     "sentiment": "positive", "intent": "praise"},
    # Competitor — Heineken (recent surge for the demo)
    {"platform": "instagram", "kind": "post", "subject_label": "Heineken",
     "author_handle": "@heineken_bo", "author_name": "Heineken Bolivia",
     "text": "🔥 Nueva alianza con la Selección — los esperamos en cada partido",
     "sentiment": "positive", "intent": "other"},
    {"platform": "instagram", "kind": "post", "subject_label": "Heineken",
     "author_handle": "@heineken_bo", "author_name": "Heineken Bolivia",
     "text": "Pop-up en Santa Cruz este finde, llevate la edición especial",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "post", "subject_label": "Heineken",
     "author_handle": "@heineken_bo", "author_name": "Heineken Bolivia",
     "text": "Hicimos un blind test contra la competencia, sorpresas vienen",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "facebook", "kind": "post", "subject_label": "Heineken",
     "author_handle": "heineken.bolivia", "author_name": "Heineken Bolivia",
     "text": "🍻 Patrocinio confirmado para el Festival Nacional de Música",
     "sentiment": "positive", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Heineken",
     "author_handle": "@brunozz", "author_name": "Bruno Z.",
     "text": "La Heineken viene fuerte con marketing últimamente",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Heineken",
     "author_handle": "@mateof", "author_name": "Mateo F.",
     "text": "Heineken te roba el aire en redes este mes",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Heineken",
     "author_handle": "@agusvv", "author_name": "Agus V.",
     "text": "La nueva campaña de Heineken con la Selección me hizo cambiar marca, lo confieso",
     "sentiment": "positive", "intent": "purchase_intent"},
    # Competitor — Corona (recent declining)
    {"platform": "instagram", "kind": "post", "subject_label": "Corona",
     "author_handle": "@corona_bo", "author_name": "Corona Bolivia",
     "text": "Verano sin Corona no es verano",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Corona",
     "author_handle": "@camisuarez", "author_name": "Cami",
     "text": "Corona se está quedando atrás en campañas, qué les pasó?",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Corona",
     "author_handle": "@floor.o", "author_name": "Floor",
     "text": "Corona sabe igual que hace 20 años pero ya no me identifica",
     "sentiment": "negative", "intent": "complaint"},
    {"platform": "facebook", "kind": "post", "subject_label": "Corona",
     "author_handle": "corona.bolivia", "author_name": "Corona Bolivia",
     "text": "Próximo evento de la marca anunciado para abril",
     "sentiment": "neutral", "intent": "other"},
    # Competitor — Stella Artois
    {"platform": "instagram", "kind": "post", "subject_label": "Stella Artois",
     "author_handle": "@stellaartois_bo", "author_name": "Stella Artois Bolivia",
     "text": "Reserva tu mesa para una experiencia premium este fin de semana",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "post", "subject_label": "Stella Artois",
     "author_handle": "@stellaartois_bo", "author_name": "Stella Artois Bolivia",
     "text": "Edición especial colaboración con chef local — sólo en La Paz",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Stella Artois",
     "author_handle": "@joaquinm.bo", "author_name": "Joaquín M.",
     "text": "Stella sigue siendo la opción premium pero el precio se fue al cielo",
     "sentiment": "neutral", "intent": "complaint"},
    # Competitor — Cerveza del Valle (artisanal, growing fast)
    {"platform": "instagram", "kind": "post", "subject_label": "Cerveza del Valle",
     "author_handle": "@cervezadelvalle", "author_name": "Cerveza del Valle",
     "text": "Nuestra IPA de mandarina ya está en 12 puntos de venta",
     "sentiment": "positive", "intent": "other"},
    {"platform": "tiktok", "kind": "post", "subject_label": "Cerveza del Valle",
     "author_handle": "@delvalle.bo", "author_name": "Cerveza del Valle",
     "text": "Visita a la fábrica: te mostramos cómo hacemos nuestra Pale Ale",
     "sentiment": "positive", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Cerveza del Valle",
     "author_handle": "@constav", "author_name": "Constanza V.",
     "text": "La IPA de Cerveza del Valle vale cada peso, es la mejor del país",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Cerveza del Valle",
     "author_handle": "@renato.cb", "author_name": "Renato",
     "text": "Cerveza del Valle viene fuerte con sus IPAs frutales",
     "sentiment": "positive", "intent": "praise"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Cerveza del Valle",
     "author_handle": "@belenccr", "author_name": "Belén C.",
     "text": "Me cambié a Cerveza del Valle hace 2 meses, no vuelvo atrás",
     "sentiment": "positive", "intent": "purchase_intent"},
    # Topic-only mentions
    {"platform": "instagram", "kind": "mention", "subject_label": "Cerveza artesanal",
     "author_handle": "@micaelao", "author_name": "Mica O.",
     "text": "La escena artesanal en BO está creciendo un montón este año",
     "sentiment": "positive", "intent": "other"},
    {"platform": "tiktok", "kind": "mention", "subject_label": "Cerveza artesanal",
     "author_handle": "@joelv", "author_name": "Joel V.",
     "text": "Probando cervezas artesanales del país: hilo en comentarios",
     "sentiment": "neutral", "intent": "other"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Fiesta y eventos",
     "author_handle": "@eventoscbba", "author_name": "Eventos Cochabamba",
     "text": "Buscamos sponsors de bebidas para festival universitario, abril 2026",
     "sentiment": "neutral", "intent": "purchase_intent"},
    {"platform": "instagram", "kind": "mention", "subject_label": "Fiesta y eventos",
     "author_handle": "@bar.laplaza", "author_name": "Bar La Plaza",
     "text": "Necesitamos proveedor de cervezas para temporada alta de verano",
     "sentiment": "neutral", "intent": "purchase_intent"},
]


INSIGHTS_SEED: list[dict[str, Any]] = [
    {
        "kind": "lead",
        "rank": 0,
        "title": "La marca está sólida pero los competidores se mueven.",
        "title_em": "Atención a Heineken y Cerveza del Valle.",
        "body": (
            "Sentimiento general estable (0,71). El lote A-2389 disparó "
            "12 quejas legítimas en 36 horas — contención necesaria. Heineken "
            "+38% en menciones esta semana por su patrocinio con la Selección; "
            "Cerveza del Valle crece 24% por boca a boca en IPAs frutales."
        ),
        "actions": [],
    },
    {
        "kind": "featured",
        "rank": 0,
        "title": "El lote A-2389 generó",
        "title_em": "12 quejas de calidad",
        "title_tail": "en 36h.",
        "body": (
            "Las quejas se concentran en La Paz y Cochabamba — coincide con la "
            "tanda enviada el martes pasado al canal moderno. Sentimiento de "
            "la marca cayó 4 pp en la franja afectada. Si respondés en las "
            "próximas 6 horas con cambio de producto + nota pública, el "
            "cluster se contiene antes de que escale a TikTok."
        ),
        "confidence": "94%",
        "age": "hace 2h",
        "impact": "Impacto: evitar viralización del reclamo en redes",
        "actions": [
            {"label": "Abrir hilo de reclamos", "route": "/inbox", "variant": "acc"},
            {"label": "Asignar a calidad", "variant": "ghost"},
        ],
    },
    {
        "kind": "memo",
        "rank": 1,
        "severity": "high",
        "tag": "Memo 01 · Competencia",
        "confidence": "Confianza 91%",
        "title": "Heineken acelera fuerte",
        "title_em": "+38% en menciones",
        "body": (
            "Su alianza con la Selección está pegando duro en redes. "
            "Pop-up confirmado en Santa Cruz este finde. Estamos viendo "
            "1-2 conversiones de marca por día en cuentas que antes "
            "interactuaban con Andina."
        ),
        "footnote": "Considerar respuesta de patrocinio antes del Mundial.",
        "actions": [{"label": "Ver detalle", "route": "/segmentos"}],
    },
    {
        "kind": "memo",
        "rank": 2,
        "severity": "high",
        "tag": "Memo 02 · Oportunidad",
        "confidence": "Confianza 86%",
        "title": "Audiencia 21-29 pidiendo",
        "title_em": "ediciones frutales",
        "body": (
            "Detectamos 47 menciones espontáneas pidiendo variantes con "
            "sabores frutales (maracuyá, mandarina). El cluster se solapa "
            "casi 1:1 con los seguidores de Cerveza del Valle — es justo el "
            "público que les estamos perdiendo."
        ),
        "footnote": "Potencial de captura: 8-12% de share en ese segmento.",
        "actions": [{"label": "Crear segmento", "variant": "acc"}],
    },
    {
        "kind": "memo",
        "rank": 3,
        "severity": "med",
        "tag": "Memo 03 · Distribución",
        "confidence": "Confianza 79%",
        "title": "Vacío en Sucre y Tarija",
        "title_em": "23 consultas sin respuesta",
        "body": (
            "23 personas preguntaron por puntos de venta en Sucre + Tarija "
            "en las últimas 2 semanas — quedaron sin respuesta. "
            "Aliarse con distribuidores locales del sur cierra esa fuga."
        ),
        "footnote": "Ver lista en /inbox filtro 'distribución'.",
        "actions": [{"label": "Ver consultas", "route": "/inbox"}],
    },
    {
        "kind": "memo",
        "rank": 4,
        "severity": "med",
        "tag": "Memo 04 · Crisis temprana",
        "confidence": "Confianza 88%",
        "title": "Críticas por suba de precio",
        "title_em": "+17 menciones en 24h",
        "body": (
            "Detectamos un pico de comentarios sobre la suba sin aviso. "
            "Aún no es viral pero tiene tono coordinado. Una nota corta "
            "explicando el ajuste (insumos, energía) en las próximas 12h "
            "tiene 70% de probabilidad de contener el escalado."
        ),
        "footnote": "Patrón similar al de marzo de 2025.",
        "actions": [{"label": "Borrador respuesta", "variant": "acc"}],
    },
    {
        "kind": "memo",
        "rank": 5,
        "severity": "low",
        "tag": "Memo 05 · B2B",
        "confidence": "Confianza 83%",
        "title": "Bares + eventos piden",
        "title_em": "cuenta corporativa",
        "body": (
            "9 establecimientos contactaron en la última semana buscando "
            "distribución directa (sin minorista intermedio). Hay valor en "
            "lanzar el programa B2B Andina aunque sea como piloto en 3 plazas."
        ),
        "footnote": "Ver listado en /inbox filtro 'B2B'.",
        "actions": [{"label": "Listar leads", "route": "/inbox"}],
    },
    {
        "kind": "memo",
        "rank": 6,
        "severity": "low",
        "tag": "Memo 06 · Producto",
        "confidence": "Confianza 76%",
        "title": "Envase nuevo genera",
        "title_em": "feedback dividido",
        "body": (
            "El rediseño tiene 58% de comentarios positivos vs 42% críticos. "
            "Las quejas se concentran en practicidad (no entra en coolers "
            "estándar). Vale revisarlo antes del rollout de invierno."
        ),
        "footnote": "Recolectar fotos de los usuarios mostrando el problema.",
        "actions": [],
    },
    {
        "kind": "memo",
        "rank": 7,
        "severity": "low",
        "tag": "Memo 07 · Performance",
        "confidence": "Confianza 81%",
        "title": "Mejor horario de respuesta",
        "title_em": "19:00-22:00 La Paz",
        "body": (
            "Las consultas comerciales que entran en esa ventana convierten "
            "2.7× más cuando responde un agente humano vs auto-respuesta. "
            "Recomendamos cubrirla con personal dedicado los jueves y viernes."
        ),
        "footnote": "Métrica sobre últimos 30 días.",
        "actions": [],
    },
    {
        "kind": "memo",
        "rank": 8,
        "severity": "med",
        "tag": "Memo 08 · Fútbol",
        "confidence": "Confianza 79%",
        "title": "Patrocinio del Tigre",
        "title_em": "buen ROI en menciones",
        "body": (
            "Los posts ligados al patrocinio generan 3.1× más engagement "
            "que el promedio de la cuenta. Pero hay 14% de críticas por "
            "publicidad invasiva en partidos. Optimizar frecuencia, no canal."
        ),
        "footnote": "Considerar reducir inserts mid-game.",
        "actions": [{"label": "Ver performance", "route": "/overview"}],
    },
    {
        "kind": "memo",
        "rank": 9,
        "severity": "high",
        "tag": "Memo 09 · Producto",
        "confidence": "Confianza 92%",
        "title": "Pedido espontáneo de",
        "title_em": "versión sin alcohol",
        "body": (
            "31 menciones específicas pidiendo una versión 0%. La audiencia "
            "incluye gente que dejó de tomar por embarazo, dieta o "
            "tratamiento — público recurrentemente perdido a no-clientes. "
            "Lanzamiento en 2026 H1 captura ese segmento antes que Heineken."
        ),
        "footnote": "Heineken 0.0 ya está disponible en BO pero sin distribución amplia.",
        "actions": [{"label": "Crear segmento", "variant": "acc"}],
    },
    {
        "kind": "memo",
        "rank": 10,
        "severity": "low",
        "tag": "Memo 10 · Inbox health",
        "confidence": "Confianza 89%",
        "title": "TMR subió a",
        "title_em": "62 minutos",
        "body": (
            "Hace 30 días el tiempo medio de respuesta era 38min. La mitad "
            "del aumento viene de reclamos del lote A-2389 sin atender. "
            "Plantillas de respuesta para los 5 tipos más frecuentes "
            "cubrirían el 70% del volumen."
        ),
        "footnote": "Ver KPI 'TMR · Kaizen' en /overview.",
        "actions": [{"label": "Ir al inbox", "route": "/inbox"}],
    },
]


# ---------------------------------------------------------------------------
# Insertion logic
# ---------------------------------------------------------------------------

async def _upsert_tenant(conn: asyncpg.Connection) -> UUID:
    tenant_id = await conn.fetchval(
        """
        INSERT INTO tenants (slug, name, status, modules, settings)
        VALUES ($1, $2, 'active', $3::jsonb, $4::jsonb)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            modules = EXCLUDED.modules,
            settings = EXCLUDED.settings
        RETURNING id
        """,
        TENANT_SLUG, TENANT_NAME,
        json.dumps({"setiq": {"tier": "pro"}, "kaizen": {"enabled": True}}),
        json.dumps({
            "meta": {
                "page_ids": ["100000000000999"],
                "instagram_business_ids": ["17841400000000999"],
            },
            "tiktok": {"handle": "@andina.beer"},
            "email": {"address": "hola@andina.example.com"},
            "channel_labels": {
                "instagram": "@cerveceriaandina",
                "facebook": "Cervecería Andina",
                "tiktok": "@andina.beer",
                "email": "hola@andina.example.com",
            },
            "ai_policy": {
                "tone_empathetic": True,
                "auto_reply_faq": False,
                "generate_recs": True,
                "daily_summary": True,
            },
        }),
    )
    return tenant_id


async def _upsert_admin(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    """Create or upsert the demo admin user and link to the tenant."""
    user_id = await conn.fetchval(
        """
        INSERT INTO users (email, password_hash, name)
        VALUES ($1, $2, 'Andina Demo')
        ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        ADMIN_EMAIL, hash_password("changeme123"),
    )
    await conn.execute(
        """
        INSERT INTO tenant_users (tenant_id, user_id, role)
        VALUES ($1, $2, 'admin')
        ON CONFLICT (tenant_id, user_id) DO UPDATE SET role = EXCLUDED.role
        """,
        tenant_id, user_id,
    )

    # Add thalma@example.com as Admin too so the tenant switcher has something
    # to flip between when logged in as thalma.
    thalma_id = await conn.fetchval(
        "SELECT id FROM users WHERE email = 'thalma@example.com' AND deleted_at IS NULL"
    )
    if thalma_id is not None:
        await conn.execute(
            """
            INSERT INTO tenant_users (tenant_id, user_id, role)
            VALUES ($1, $2, 'admin')
            ON CONFLICT (tenant_id, user_id) DO UPDATE SET role = EXCLUDED.role
            """,
            tenant_id, thalma_id,
        )


async def _wipe_tenant_data(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    """Drop only the seedable data — keep the tenants/users/tenant_users rows."""
    await conn.execute("DELETE FROM mention_classifications WHERE tenant_id = $1", tenant_id)
    await conn.execute("DELETE FROM mentions WHERE tenant_id = $1", tenant_id)
    await conn.execute("DELETE FROM message_classifications WHERE tenant_id = $1", tenant_id)
    await conn.execute("DELETE FROM messages WHERE tenant_id = $1", tenant_id)
    await conn.execute("DELETE FROM conversations WHERE tenant_id = $1", tenant_id)
    await conn.execute("DELETE FROM channel_identities WHERE tenant_id = $1", tenant_id)
    await conn.execute("DELETE FROM contacts WHERE tenant_id = $1", tenant_id)
    await conn.execute("DELETE FROM tracked_subjects WHERE tenant_id = $1", tenant_id)
    await conn.execute("DELETE FROM insights WHERE tenant_id = $1", tenant_id)


async def _insert_tracked_subjects(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    for s in TRACKED_SUBJECTS:
        await conn.execute(
            """
            INSERT INTO tracked_subjects (
                tenant_id, kind, label, handles, keywords, hashtags, enabled
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, true)
            """,
            tenant_id, s["kind"], s["label"],
            json.dumps(s["handles"]), s["keywords"], s["hashtags"],
        )


async def _insert_contacts(conn: asyncpg.Connection, tenant_id: UUID) -> tuple[list[UUID], dict[tuple[UUID, str], UUID]]:
    contact_ids: list[UUID] = []
    identity_map: dict[tuple[UUID, str], UUID] = {}
    for c in CONTACTS:
        primary_email = c["handles"].get("email")
        cid = await conn.fetchval(
            """
            INSERT INTO contacts (
                tenant_id, display_name, primary_email,
                profile_data, tags, first_seen_at, last_seen_at
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            RETURNING id
            """,
            tenant_id, c["name"], primary_email,
            json.dumps({"source": "seed_sample"}), [],
            NOW - timedelta(days=random.randint(30, 365)), NOW,
        )
        contact_ids.append(cid)
        for platform, handle in c["handles"].items():
            ident_id = await conn.fetchval(
                """
                INSERT INTO channel_identities (
                    tenant_id, contact_id, channel, external_id, display_name, verified
                ) VALUES ($1, $2, $3, $4, $5, false)
                RETURNING id
                """,
                tenant_id, cid, platform, handle, c["name"],
            )
            identity_map[(cid, platform)] = ident_id
    return contact_ids, identity_map


def _identity_channel_for(conv_channel: str) -> str:
    if conv_channel.startswith("instagram"): return "instagram"
    if conv_channel.startswith("facebook"):  return "facebook"
    if conv_channel.startswith("tiktok"):    return "tiktok"
    if conv_channel == "email":              return "email"
    return "web"


async def _insert_message_classifications(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    message_id: UUID,
    intent: str,
    sentiment: str,
    sent_at: datetime,
) -> None:
    classified_at = sent_at + timedelta(seconds=random.randint(2, 30))
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


async def _insert_conversations_and_messages(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    contact_ids: list[UUID],
    identity_map: dict[tuple[UUID, str], UUID],
) -> None:
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
        channel = theme["channel"]
        ident_channel = _identity_channel_for(channel)
        eligible = [c for c in contact_ids if (c, ident_channel) in identity_map]
        if not eligible:
            continue
        n_contacts = min(theme["n_contacts"], len(eligible))
        contacts_in_thread = random.sample(eligible, n_contacts)
        msgs_per_contact = max(1, theme["n_messages"] // n_contacts)

        bucket = random.random()
        if bucket < 0.5:    days_back = random.randint(1, 10)
        elif bucket < 0.8:  days_back = random.randint(11, 30)
        else:               days_back = random.randint(31, 60)
        base_time = NOW - timedelta(days=days_back)

        for c_idx, contact_id in enumerate(contacts_in_thread):
            identity_id = identity_map[(contact_id, ident_channel)]
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
                    f"andina_{msg_seq:05d}", sent_at,
                    '{"source": "seed_sample"}',
                )
                await _insert_message_classifications(
                    conn, tenant_id, msg_id, intent, sentiment, sent_at,
                )

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
                            f"andina_{msg_seq:05d}", reply_at,
                            '{"source": "seed_sample"}',
                        )

            await conn.execute(
                "UPDATE conversations SET last_message_at = (SELECT MAX(sent_at) FROM messages WHERE conversation_id = $1) WHERE id = $1",
                conv_id,
            )


async def _insert_mentions(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    sub_rows = await conn.fetch(
        "SELECT id, label FROM tracked_subjects WHERE tenant_id = $1",
        tenant_id,
    )
    subject_by_label = {r["label"]: r["id"] for r in sub_rows}

    for idx, m in enumerate(MENTIONS):
        sub_id = subject_by_label.get(m["subject_label"])
        if sub_id is None:
            continue
        bucket = random.random()
        if bucket < 0.6:    days_ago = random.randint(0, 6)
        elif bucket < 0.9:  days_ago = random.randint(7, 13)
        else:               days_ago = random.randint(14, 30)
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
            m["text"], f"https://example.com/{m['platform']}/andina_seed_{idx:03d}",
            published,
            json.dumps({
                "likes": random.randint(0, 1500),
                "comments_count": random.randint(0, 200),
                "shares": random.randint(0, 100),
            }),
            f"andina_seed_mention_{idx:03d}",
            '{"source": "seed_sample"}',
            f"andina_seed_run_{idx // 10:02d}",
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


async def _insert_insights(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    for s in INSIGHTS_SEED:
        await conn.execute(
            """
            INSERT INTO insights (
                tenant_id, kind, severity, tag, title, title_em, title_tail,
                body, confidence, age, impact, footnote, actions, rank, enabled
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14, true)
            """,
            tenant_id, s["kind"], s.get("severity"), s.get("tag"),
            s["title"], s.get("title_em"), s.get("title_tail"),
            s["body"], s.get("confidence"), s.get("age"), s.get("impact"),
            s.get("footnote"),
            json.dumps(s.get("actions") or []),
            s.get("rank", 0),
        )


async def _print_summary(conn: asyncpg.Connection, tenant_id: UUID) -> None:
    queries = {
        "tracked_subjects":      "SELECT COUNT(*) FROM tracked_subjects WHERE tenant_id = $1",
        "contacts":              "SELECT COUNT(*) FROM contacts WHERE tenant_id = $1",
        "channel_identities":    "SELECT COUNT(*) FROM channel_identities WHERE tenant_id = $1",
        "conversations":         "SELECT COUNT(*) FROM conversations WHERE tenant_id = $1",
        "messages":              "SELECT COUNT(*) FROM messages WHERE tenant_id = $1",
        "message_classifications":"SELECT COUNT(*) FROM message_classifications WHERE tenant_id = $1",
        "mentions":              "SELECT COUNT(*) FROM mentions WHERE tenant_id = $1",
        "mention_classifications":"SELECT COUNT(*) FROM mention_classifications WHERE tenant_id = $1",
        "insights":              "SELECT COUNT(*) FROM insights WHERE tenant_id = $1",
    }
    print(f"\nSeeded sample data for tenant '{TENANT_SLUG}' ({TENANT_NAME}):")
    for label, q in queries.items():
        n = await conn.fetchval(q, tenant_id)
        print(f"{label:>28} {n:>5}")


async def main() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        async with conn.transaction():
            tenant_id = await _upsert_tenant(conn)
            await _upsert_admin(conn, tenant_id)
            await _wipe_tenant_data(conn, tenant_id)
            await _insert_tracked_subjects(conn, tenant_id)
            contact_ids, identity_map = await _insert_contacts(conn, tenant_id)
            await _insert_conversations_and_messages(conn, tenant_id, contact_ids, identity_map)
            await _insert_mentions(conn, tenant_id)
            await _insert_insights(conn, tenant_id)
            await _print_summary(conn, tenant_id)
        print(f"\nLogin demo:  {ADMIN_EMAIL} / changeme123")
        print("Tenant switcher: thalma@example.com is also admin of this tenant.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
