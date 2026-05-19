# Plan por etapas — MVP de SETIQ

Pasos secuenciales para llevar SETIQ desde "tres amigos sin empresa" hasta "cliente pago (ITALSA) en producción". Cada etapa lista quién hace qué.

## Equipo

| Persona | Rol en el proyecto | Rol en la Meta App |
|---|---|---|
| **Roger** | Co-fundador técnico, owner del repo, backend lead | **Admin** (crea la app) |
| **Saul** | Co-fundador técnico | **Developer** (acepta invitación de Roger) |
| **Thalma** | Co-fundadora + piloto MVP (periodista / influencer con audiencia real) | **Tester** (sólo necesita su cuenta personal de FB) |

**Estado legal:** ninguna empresa formada todavía. Tres amigos. La incorporación se difiere hasta antes de firmar el primer cliente pago. Hasta entonces todo corre en modo development sobre cuentas personales.

---

## Etapa 0 — Preparación de cuentas (día 0, ~1 hora)

### Roger
1. Crear cuenta de Meta Developer en [developers.facebook.com](https://developers.facebook.com) usando su cuenta personal de Facebook.
2. Aceptar los términos de developer.
3. Crear un Meta Business Manager en [business.facebook.com](https://business.facebook.com). El nombre puede ser "SETIQ" o similar. **No iniciar Business Verification todavía** (eso requiere empresa real).

### Saul
1. Tener su cuenta personal de Facebook activa. Nada más por ahora — la invitación que le mandará Roger lo registra automáticamente como Developer al aceptarla.

### Thalma
1. Confirmar que su Instagram esté en modo **Business** o **Creator** (no Personal). Configuración en la app de IG → Settings → Account type.
2. Confirmar que tenga una **Facebook Page** asociada a su proyecto. Si no, crear una (no usar su perfil personal — Meta no permite leer datos de perfiles personales vía API).
3. **Linkear su IG Business con su Facebook Page**: en la app de IG → Settings → Business → Connect Facebook Page.
4. (Opcional pero recomendado) Convertir su cuenta de TikTok a Business — ayuda con algunos actors de Apify.
5. Armar lista de **tracked subjects** para alimentar la rama de monitoreo off-property:
   - **Brand** — keywords y hashtags que identifican su marca personal / proyecto (para encontrar menciones donde no la taguean directamente).
   - **Competidores** — 3-5 perfiles de IG / FB / TikTok de creadoras o medios contra los que ella quiere benchmarkearse (post frequency, sentiment de audiencia, share-of-voice).
   - **Keywords / hashtags temáticos** — temas que cubre y le interesa monitorear cómo se está hablando de ellos.

### Lo que NO se hace en esta etapa
- ❌ Business Verification (requiere NIT / empresa formada).
- ❌ Incorporar empresa.
- ❌ App Review.
- ❌ WhatsApp Business setup.

---

## Etapa 1 — Crear la Meta App (día 1, ~1 hora)

### Roger
1. En [developers.facebook.com](https://developers.facebook.com) → **My Apps** → **Create App**.
2. Tipo: **Business**.
3. Nombre: `SETIQ` (o el nombre comercial final).
4. Asociar al Business Manager creado en Etapa 0.
5. Agregar productos a la app:
   - **Facebook Login** (para OAuth)
   - **Webhooks**
   - **Instagram Graph API**
   - **Messenger Platform**
6. La app queda en **Development Mode** automáticamente — exactamente lo que queremos.
7. Anotar el `App ID` y `App Secret` — van en el `.env` del backend.

### Invitar al equipo
1. En la app → **Roles** → **Add People**:
   - Saul → **Developer**
   - Thalma → **Tester**
2. Saul y Thalma reciben email con link de aceptación. Aceptan.

---

## Etapa 2 — Conectar las cuentas de Thalma a la app (días 2-3)

### Roger (backend)
1. Levantar un túnel público hacia el backend local (necesario porque Meta exige HTTPS para webhooks):
   - **Cloudflare Tunnel** (gratis, URL estable): `cloudflared tunnel --url http://localhost:8000`.
   - O **ngrok** (gratis, URL cambia en cada arranque salvo plan pago).
2. Configurar webhooks en la Meta App:
   - **Pages** → suscribir a eventos `feed` (comentarios) y `messages` (Messenger DMs). Callback URL: `https://<tunnel>/webhooks/meta`. Verify token: cualquier string secreto.
   - **Instagram** → suscribir a `comments`, `messages`. Misma callback URL.
3. Implementar el verify handshake en `/webhooks/meta` (FastAPI debe responder al GET de Meta con el `hub.challenge`).

### Thalma
1. Abrir el link de OAuth que le manda Roger (formato `https://www.facebook.com/v18.0/dialog/oauth?...`).
2. Aprobar los permisos: `pages_show_list`, `pages_messaging`, `pages_read_engagement`, `pages_manage_metadata`, `instagram_basic`, `instagram_manage_messages`, `instagram_manage_comments`.
3. Confirmar a Roger.

### Validación
1. Thalma publica un comentario de prueba en uno de sus posts de IG.
2. Roger verifica que el webhook llegue a `/webhooks/meta` y se guarde un row en `webhook_events`.
3. Si llega: ✅ Etapa 2 cerrada. Si no llega: revisar tunnel + permisos.

---

## Etapa 3 — Apify para off-property + TikTok + monitoreo de competidores (paralelo a Etapas 1-2, días 1-5)

Apify cubre **tres usos distintos** en el MVP, todos sobre el mismo setup técnico:

1. **TikTok de Thalma** — TikTok no tiene API oficial útil; Apify es la única vía.
2. **Posts públicos de competidores** — IG / FB / TikTok de los handles que Thalma listó como competidores en Etapa 0. Persistimos como `mentions` con `kind='post'`.
3. **Menciones de la marca off-property** — keywords / hashtags que Thalma listó. Persistimos como `mentions` con `kind='mention'`.

### Roger o Saul
1. Crear cuenta en [apify.com](https://apify.com). Plan gratuito alcanza para empezar (~US$5/mes de créditos free).
2. Generar API token en Settings → Integrations.
3. Elegir actors:
   - **TikTok del cliente** — `clockworks/tiktok-scraper` con el handle de Thalma → resultados al schema de canales (`messages` con `channel='tiktok_comment'` + `channel_identities` con `channel='tiktok'`).
   - **Posts de competidores en IG** — `apify/instagram-scraper` con los handles competidores → `mentions` (`platform='instagram'`, `kind='post'`, FK a `tracked_subjects` de tipo `competitor`).
   - **Posts de competidores en FB** — `apify/facebook-posts-scraper` → `mentions` (`platform='facebook'`).
   - **Posts de competidores en TikTok** — `apidojo/tiktok-scraper` o similar → `mentions` (`platform='tiktok'`).
   - **Búsquedas por keyword / hashtag** — actor de búsqueda en IG / web → `mentions` (`kind='mention'`).
4. Probar cada actor manualmente en la UI de Apify — verificar resultados.
5. Implementar workers Arq que disparan los actors según schedule:
   - TikTok del cliente: cada 2-4 horas.
   - Competidores: cada 4-12 horas.
   - Brand keywords / hashtags: cada 1-2 horas.
6. Consumir resultados vía la API de Apify (`GET /v2/datasets/<id>/items`).
7. Persistir según el destino correspondiente (`messages` para canales propios del cliente, `mentions` para todo lo demás).
8. Encolar clasificación con Claude para cada nueva fila (intent / sentiment / opportunity).

### Configuración por tenant
Los actors leen su lista de objetivos desde la tabla `tracked_subjects` filtrada por `tenant_id` (creada en migración #6). El admin UI (Etapa 4) permite editarla.

### No requiere
- Business Verification.
- Meta App Review.
- Cuenta de TikTok Developer (la API oficial no sirve para nuestro caso).
- Ningún OAuth con los competidores (sólo leemos contenido público).

---

## Etapa 4 — Construir el MVP backend + frontend (días 5-20)

### Roger (backend, FastAPI)
1. Crear rol Postgres no-superuser (`setiq_app`) para que RLS opere de verdad en runtime.
2. Implementar auth JWT + middleware que setea `SET LOCAL app.current_tenant = '<uuid>'` por request.
3. Endpoints iniciales:
   - `POST /auth/login`, `GET /auth/me`.
   - `POST /webhooks/meta` (verify + handler).
   - `POST /webhooks/apify` o worker que pollea.
   - `GET /conversations`, `GET /conversations/{id}/messages`.
   - `POST /conversations/{id}/reply` (KAIZEN: postea respuesta vía la API correspondiente).
   - `GET /tracked-subjects`, `POST /tracked-subjects`, `PATCH /tracked-subjects/{id}` — admin de competidores / brand / keywords.
   - `GET /mentions` — listado paginado de posts/menciones off-property con filtros (tracked_subject, platform, sentiment, fecha).
4. Seed inicial: un tenant para Thalma + ella como user admin + sus tracked_subjects pre-cargados desde la lista de Etapa 0.
5. Workers Arq:
   - **Clasificación de mensajes** — toma cada nuevo `messages` row → Claude → guarda en `message_classifications`.
   - **Clasificación de menciones** — toma cada nuevo `mentions` row → Claude → guarda en `mention_classifications`.
   - **Apify dispatch** — cada N horas dispara los actors configurados según `tracked_subjects` enabled.

### Saul (frontend, Angular 21) o backend (paired)
1. Bootstrap `setiq-web` (separate repo) — Angular CLI, standalone components, signals.
2. Login screen + auth flow.
3. **Dashboard SETIQ core (canales propios)**: volumen de mensajes por canal, distribución de sentiment, top intents, lista de usuarios más activos.
4. **Competitive landscape / Off-property mentions** (sobre `mentions` + `mention_classifications`): post frequency por competidor, share-of-voice por keyword, sentiment de la audiencia de cada competidor, feed de menciones recientes de la marca.
5. **Inbox KAIZEN**: lista de conversaciones, vista de mensajes, composer para responder.
6. **Admin → Tracked subjects**: UI para que Thalma agregue/edite competidores, brand keywords y hashtags monitoreados.
7. Cliente API generado desde el OpenAPI de FastAPI vía `openapi-generator` o `orval`.

### Thalma
1. Usar el inbox durante una semana para responder comentarios reales desde la plataforma.
2. Anotar qué funciona, qué falta, qué clasificación está mal.
3. Dar feedback de UX (Roger / Saul ajustan).

---

## Etapa 5 — Validación interna (días 20-30)

- Thalma usa SETIQ una semana entera en producción interna (todavía dev mode, sólo ella).
- Comparar lo que el dashboard de SETIQ dice vs lo que ella ya sabía intuitivamente sobre su audiencia.
- Ajustar prompts de clasificación de Claude hasta que los intents / sentiments sean útiles.
- Listar bugs y casos edge.
- Decidir si el producto está listo para mostrar a ITALSA o si hace falta otra iteración.

---

## Etapa 6 — Decidir incorporar empresa (solo cuando ITALSA esté cerca)

**Disparadores que activan esta etapa:**
- El MVP funciona técnicamente.
- Hay conversaciones serias con ITALSA u otro cliente potencial.
- ITALSA dice "queremos avanzar / firmar".

**Pasos:**
1. Reunión con contador. Decidir estructura legal en Bolivia:
   - **Unipersonal** (Roger personal) — más barato y rápido, registro en FUNDEMPRESA + NIT. Buena opción si el ingreso inicial es chico y Roger factura solo.
   - **SRL** — costo de constitución mayor + contador mensual. Hace falta si los tres comparten equity formalmente o si los contratos exigen empresa.
2. Constituir en FUNDEMPRESA.
3. Obtener NIT en Impuestos Nacionales.
4. Hacer Business Verification en Meta Business Manager — subir documentos legales. Tarda 2-5 días hábiles.

---

## Etapa 7 — App Review + ir a producción (3-6 semanas)

### Roger
1. Tener Privacy Policy y Terms of Service en URLs públicas reales (puede ser una landing simple).
2. Grabar video demo end-to-end usando la cuenta de Thalma:
   - Login en SETIQ.
   - Inbox mostrando comentarios + DMs reales.
   - Responder un comentario desde el inbox → el comentario aparece en la cuenta de Thalma.
   - Dashboard mostrando clasificación + métricas.
3. Escribir el use case description: **"Customer engagement / interaction management platform for businesses"** — descripción amplia, NO descripción específica de "tool para influencer".
4. Submit App Review en developers.facebook.com → App Review → Permissions and Features.
5. Responder rondas de clarificación (Meta suele pedir 1-3 ajustes).

**Cuando esté aprobada:**
- Cambiar la app a **Live Mode**.
- Listo para onboardear ITALSA.

---

## Etapa 8 — Onboardear ITALSA en producción

1. Sales process aparte: cerrar el deal con ITALSA.
2. ITALSA hace su propia Business Verification en Meta (sus documentos legales).
3. Roger les manda link de OAuth → ITALSA acepta conectar sus Pages + IG Business + cuenta de WhatsApp.
4. Crear tenant ITALSA en la DB. Activar módulo KAIZEN en `tenants.modules`.
5. (Sólo ITALSA) Agregar producto **WhatsApp Business** a la Meta App:
   - Provisionar número de teléfono dedicado de ITALSA.
   - Crear y submit message templates.
   - Esperar aprobación (1-3 semanas adicionales).
6. ITALSA entra en producción.

---

## Resumen de timeline

| Período | Hito |
|---|---|
| Día 0-1 | Cuentas personales + Meta App creada |
| Día 2-3 | Webhooks de Meta funcionando contra cuentas de Thalma |
| Día 1-3 (paralelo) | TikTok ingestion vía Apify funcionando |
| Día 5-20 | MVP backend + frontend implementados |
| Día 20-30 | Validación interna con Thalma |
| Día 30+ | (cuando ITALSA esté cerca) Incorporar empresa, Business Verification, App Review |
| Semana 4-10 después de submit | App approval, ir a Live Mode, onboardear ITALSA |

---

## Cosas que NO hacer todavía

- ❌ Incorporar empresa antes de tener cliente real cerca de firmar.
- ❌ Business Verification antes de incorporar.
- ❌ App Review antes de tener MVP probado con Thalma.
- ❌ WhatsApp Business setup antes de cerrar con ITALSA.
- ❌ Hetzner deploy hasta que el MVP corra estable en local.
- ❌ Construir tabla `mentions` separada — el schema actual (`conversations` + `messages`) cubre todo lo que necesitamos para el MVP.
