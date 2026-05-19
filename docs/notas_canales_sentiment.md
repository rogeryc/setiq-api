# Notas técnicas — sentiment, canales privados y social listening

Tres puntos del plan técnico del proyecto.

## 1. Sentiment — fácil

Se obtiene con un LLM, no con un modelo entrenado a medida. En el diseño:

- Cada mensaje o mención que entra se manda a Claude con un prompt tipo "clasifica esto en `positive / neutral / negative` y devuelve confidence 0-1".
- El resultado se guarda en una tabla `classifications` con `kind='sentiment'`, junto con `intent`, `priority`, `opportunity`, `language`.
- Es un job de fondo (Arq worker): el ingestor persiste el ítem, encola la clasificación, el worker llama a Claude, guarda el resultado.

Costo: centavos por mensaje. No hay que entrenar nada.

## 2. Canales privados (KAIZEN) — APIs oficiales, sí o sí

Para WhatsApp, Instagram DMs, Facebook Messenger, email y teléfono — **no se scrapea, se integra con la API oficial**.

| Canal | Cómo se conecta | Qué se necesita |
|---|---|---|
| **WhatsApp Business** | Meta Cloud API o un BSP (Twilio, 360dialog) | Verificación de Meta Business + número dedicado + templates aprobados |
| **Instagram DMs** | Meta Graph API (Instagram Messaging) | Cuenta business linkeada a una Facebook Page + permiso `instagram_manage_messages` |
| **Facebook Messenger** | Meta Graph API (Messenger Platform) | Facebook Page + webhook + app review de Meta |
| **Email** | IMAP/SMTP, o proveedor como Postmark/SendGrid (inbound parse) | Cuenta SMTP del cliente o dominio MX configurado |
| **0800 / teléfono** | Twilio Voice / proveedor SIP | Número provisionado + transcripción (Whisper / AssemblyAI) |

Lo bloqueante acá no es código, es **trámite con Meta** (2-3 semanas de calendario por aprobaciones). Por eso conviene arrancar el papeleo en paralelo y construir el MVP contra **email** primero, que se levanta en días sin depender de aprobaciones externas.

## 3. Social listening (SETIQ core)

Este es el producto que compra la mayoría de clientes (no sólo ITALSA): **medir qué tan aceptada está una marca / producto en redes sociales**, en vez de pagar US$10k a una encuestadora.

### Lo clave: si el cliente conecta sus cuentas, accedemos a casi todo lo que importa

Cuando un cliente nos da acceso OAuth a su Meta Business (Facebook Page + Instagram Business), **podemos leer**:

| Dato | ¿Accesible? | Notas |
|---|---|---|
| Posts propios del cliente (FB + IG) | ✅ | Todo lo que publicaron |
| **Comentarios que la gente deja en esos posts** | ✅ | **Esto es lo central del producto** |
| Replies a esos comentarios | ✅ | Thread completo |
| Reactions / likes por post | ✅ | Métricas agregadas |
| DMs entrantes (Messenger + IG DM) | ✅ | Esto es KAIZEN |
| @menciones de la cuenta del cliente | ✅ | Cuando alguien lo tagea |
| Insights / reach / engagement | ✅ | Page Insights API |
| Búsqueda por hashtag | ⚠️ Limitada | IG Graph API: máx 30 hashtags / 7 días |

Lo que **NO** podemos leer (esto es lo que Meta bloquea):

| Dato | ¿Accesible? | Por qué |
|---|---|---|
| Posts de gente random no relacionada al cliente | ❌ | No es contenido del cliente |
| Lo que un comentarista dice en otra parte de la plataforma | ❌ | Restricción de privacidad |
| Datos de perfil del comentarista más allá del nombre + handle | ❌ | Bloqueado desde 2018 (Cambridge Analytica) |

### Por qué esto cambia el análisis

Lo accesible cubre **la mayoría** de lo que las encuestadoras realmente miden: "qué dice mi gente sobre mí en mis propios canales". Un comentario tipo "este producto es horrible" en un post de IG de ITALSA es exactamente la señal que el cliente quiere capturar. No necesitamos hackear nada, ni jugar a la zona gris — basta con que el cliente nos conecte sus cuentas.

### Implicación de modelo de datos

El producto **comparte shape con KAIZEN**: comentarios + DMs son interacciones con un contacto, encajan en `contacts → channel_identities → conversations → messages` con `channel` distinguiendo `instagram_comment` de `instagram_dm`. La diferencia es de UI/workflow:

- **KAIZEN** = humanos responden esos comentarios/DMs desde un inbox (workflow ITALSA)
- **SETIQ core** = los mismos datos ingestados, pero sin UI de reply — sólo dashboards y clasificación

## Resumen operativo

1. El MVP se construye sobre el mismo schema (`contacts/channel_identities/conversations/messages`) que KAIZEN — sin schema paralelo.
2. **MVP de KAIZEN** para ITALSA: empezar por **email** (sin trámites Meta), agregar WhatsApp/IG/FB cuando Meta apruebe.
3. **Papeleo Meta en paralelo** desde día 1 — necesario tanto para ITALSA (KAIZEN) como para cada cliente que conectemos a SETIQ.
4. Ver `checklist_integraciones.md` para el detalle por canal de qué trámite hace falta y qué alternativa (Apify) existe.
