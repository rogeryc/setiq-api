# SETIQ — TODO

Lista de tareas pendientes en ambos repos + cosas externas (papeleo, cuentas).
Actualizar al final de cada sesión.

**Última actualización:** 2026-06-23 PM (Saul + Claude) — deploy a prod en OVH VPS + CI/CD GitHub Actions + integración Meta configurada en dashboard + pipeline de IA real (clasificación + generador de insights + clasificación de menciones) vía LiteLLM (Llama sandbox / Claude por cliente). Ver "Estado actual" abajo. **Handoff para Roger: leer esa sección primero.**

---

## Prioridad actual (2026-05-28 · Saul)

- **Hacer ahora:** todo lo que NO esté bloqueado por cuentas externas — endpoints de escritura del backend, interactividad del frontend, y calidad (tests/CI/logging).
- **Apify → al final:** sólo aporta data de TikTok + competidores; no bloquea el resto del MVP.
- **WhatsApp → no considerar todavía:** depende de App Review + cliente con número; fuera de alcance por ahora.
- **Hecho 2026-05-28 (branch `saul`):** el parser de webhooks ya maneja las 4 superficies de Meta — IG comments + IG DMs, FB comments + FB Messenger (`src/setiq/ingestion/parser.py`). Antes sólo parseaba IG comments.
- **Hecho 2026-06-21 (Roger, merged a `main`):** integración Meta completa del lado código (ver detalle abajo en Backend → Integración Meta y Frontend). Lo único que falta para que fluya data real es **configuración en el dashboard de Meta + App Review**, no código. Pasos en `docs/meta_app_setup.md`.
- **Lo que queda accionable AHORA (sin bloqueo externo):** crear/configurar la Meta App en el dashboard, completar `META_*` en `.env`, y probar el OAuth end-to-end contra las cuentas de Thalma vía ngrok (`docs/meta_app_setup.md` §1-7).

---

## Estado actual (2026-06-23 PM · Saul + Claude) — HANDOFF

### Infra / deploy (HECHO)
- Stack en **OVHcloud VPS `149.56.44.13`** vía Docker Compose: postgres + redis + **api** (FastAPI) + **web** (Angular SSR) + **caddy** + **worker** (Arq).
- `https://api.setiq.lat` (backend) · `https://app.setiq.lat` (frontend) · HTTPS auto (Caddy). `setiq.lat`/`www` → landing en Firebase (live).
- Seed cargado (Thalma + Cervecería Andina). Logins: `thalma@example.com` / `changeme123`, `demo@andina.example.com` / `changeme123`.
- **CI/CD GitHub Actions:** flujo `saul` → PR → `main`. CI (ruff/mypy/pytest + web build) corre en PRs a main; **CD deploya a la VPS en cada merge a main** (api: rsync→build→migrate dbmate→restart api+worker; web: build→restart). Secrets `VPS_HOST/USER/SSH_KEY` ya seteados.
- Runbook + cómo redeployar/migrar/seed: `deploy/README.md`. Compose versionado en `setiq-api/deploy/`.
- ⚠️ **Cambios de estructura del compose NO los reaplica el CD** (sólo rebuild/restart). Si agregás un servicio, actualizá el `docker-compose.yml` del server a mano (`/home/ubuntu/setiq/`).

### Meta (configurado en dashboard, código completo)
- App Empresa `META_APP_ID=1728486774842629`. 3 casos de uso (IG, Página, Messenger), OAuth redirect, webhooks, testers (Thalma + Roger). Permisos IG por **Facebook Login** habilitados.
- `OAUTH_SCOPES` final: `pages_show_list, pages_read_engagement, pages_messaging, pages_manage_metadata, instagram_basic, instagram_manage_comments, instagram_manage_messages, business_management`. Diálogo abre OK.
- Tokens en tabla **`connected_channels`** (RLS, Fernet) — ya NO en `tenants.settings` JSONB.
- **Pendiente:** [ ] completar una conexión REAL (Thalma autoriza su cuenta con FB Page+IG); [ ] App Review (bloqueado por incorporación de empresa).

### Pipeline de IA (HECHO — real, no placeholder)
- Classifier **pluggable vía LiteLLM** (`CLASSIFIER_MODEL`): sandbox = `groq/llama-3.3-70b-versatile` (GRATIS, `GROQ_API_KEY` seteado en el server), prod por cliente = `anthropic/claude-haiku-4-5` (`ANTHROPIC_API_KEY`). **Switch = una env var, sin código.** (Kimi NO está en Groq; para Kimi sería OpenRouter.)
- Worker corre 2 jobs + 2 crons: `classify_message`, `classify_mention`, `generate_insights`; crons `cleanup_webhook_events` (3am UTC) y `generate_all_insights` (4am UTC).
- **Clasificación de mensajes:** real (Llama) — seed de Thalma backfilleado.
- **Generador de insights/recomendaciones:** `ai/insights_generator.py` — agrega data real del tenant → LLM → lead+featured+memos. Reemplaza los insights hand-written del seed.
- **Clasificación de menciones:** `classify_mention` — real (Llama); backfill de menciones del seed en curso.
- ⚠️ **Modelo es GLOBAL, no per-tenant todavía.** Hoy TODOS los tenants usan `CLASSIFIER_MODEL`. Para "test→Llama / cliente real→Claude" simultáneo falta **per-tenant model routing** (guardar el modelo en `tenants.settings.ai.classifier_model` y leerlo por mensaje). Diferido (Saul ok con Llama-para-todos por ahora).

### Env vars clave en el `.env` del server (`/home/ubuntu/setiq/.env`)
`GROQ_API_KEY`=set · `CLASSIFIER_MODEL`=groq/llama-3.3-70b-versatile · `ANTHROPIC_API_KEY`=blank (setear por cliente pago) · `META_APP_ID/SECRET`=set · `META_WEBHOOK_VERIFY_TOKEN`/`META_TOKEN_ENCRYPTION_KEY`/`JWT_SECRET`/`POSTGRES_PASSWORD`=generados.

### Lo que sigue (sin bloqueo externo, código)
- [ ] Per-tenant model routing (test→Llama / cliente→Claude).
- [ ] Sentry/Logtail. [ ] Backups Postgres → Backblaze B2 (antes de data real). [ ] Refrescar contenido del landing. [ ] Env separation dev/staging/prod.

### Bloqueado por cuenta/key (Roger)
- [ ] Apify (worker TikTok/competidores + botón "Sincronizar todo"). [ ] Postmark (email inbound). [ ] `ANTHROPIC_API_KEY` con saldo (para correr clientes en Claude).

### Bloqueado por Thalma / incorporación
- [ ] Conexión Meta real + test IG (Thalma). [ ] Lista definitiva de competidores/keywords. [ ] Video demo. [ ] App Review → WhatsApp + Live mode (requiere empresa incorporada).

---

## Roadmap AI Product + Mobile (2026-06-24 · secuencia priorizada)

> Objetivo: pasar de "dashboard con labels de IA" a **producto AI-native**. Orden: polish → salto de producto → moat → conversacional/ongoing. **Mobile es transversal** (arreglar todas las páginas; el Inbox está bug). Auditoría UI/UX hecha contra la app live 2026-06-24.

### Fase 0 — Polish (que la IA que ya está se sienta terminada)
- [ ] Headline del insight `lead` gramatical: el generador debe devolver UN titular limpio (o title + subtítulo), no pegar `title_em` y armar oraciones run-on (ej. "…Thalma Roca sentimiento neutral y positivo"). Ajustar prompt en `ai/insights_generator.py` + render.
- [ ] Labels de clasificación en español en TODA la UI (intent/sentiment/priority): Queja / Negativo / Alta, etc. Hoy el detalle del Inbox muestra `complaint/negative/high` en inglés y los chips en español → unificar en la capa de display.
- [ ] Inbox: distinguir visualmente inbound vs outbound (lado/color); hoy los mensajes se ven idénticos.
- [ ] Reemplazar el "— actualizando…" persistente del masthead por un indicador sutil y transitorio.
- [ ] Insights accionables: renderizar los botones `actions` en Recomendaciones (no sólo en el dashboard) + deep-link al Inbox/segmento filtrado.
- [ ] Insights con evidencia: mostrar "basado en N mensajes/menciones" + link a la data detrás de cada insight.
- [ ] Dashboard: selector de rango temporal (7 / 30 / 90 días) en vez de fijo.
- [ ] Dashboard: priorizar "lo que necesita atención" (sin resolver / negativos) antes de las métricas vanity.

### Fase 1 — Salto de producto (lo que el comprador siente)
- [ ] ⭐ **Respuestas redactadas por IA** en el composer del Inbox: sugerir respuesta usando la conversación + su clasificación + voz de marca; el agente edita y envía (LiteLLM, mismo model config).
- [ ] Ajustes de voz/tono de marca por tenant (alimenta el prompt de respuesta).
- [ ] Alertas proactivas: detectar caída de sentiment / cluster de quejas / spike negativo.
- [ ] Entrega de alertas: in-app + email (WhatsApp después).
- [ ] Digest semanal por IA enviado por email (el "Resumen del lunes" como mail real, no sólo página).

### Fase 2 — Moat (defensibilidad + escala multi-cliente)
- [ ] Contexto/taxonomía de IA por tenant (`tenants.settings.context`: industria, categorías de audiencia/temas) + `PATCH /tenants/me/context` + form de onboarding por industria.
- [ ] Refactor de prompts (classifier + insights) para leer el contexto del tenant en vez de hardcodear categorías.
- [ ] Auto-temas / clustering de quejas + menciones en tópicos emergentes (ej. envío, precio) + trend en el tiempo.
- [ ] Closed-loop learning: capturar correcciones de labels del agente + respuestas editadas como señal.
- [ ] Evidencia/citations (grounding tipo RAG) en cada insight y respuesta de IA.
- [ ] Per-tenant model routing (test→Llama / cliente real→Claude vía `tenants.settings.ai.classifier_model`).

### Fase 3 — Conversacional + ongoing
- [ ] "Pregúntale a tu data": analítica conversacional sobre la data del tenant (estilo ⌘K), respuestas grounded + links.
- [ ] Tracking de costo/uso de LLM por tenant.
- [ ] Sentry / Logtail para errores.
- [ ] Backups de Postgres → Backblaze B2.
- [ ] Refrescar contenido del landing (`setiq.lat`).
- [ ] Env separation dev / staging / prod.

### Mobile responsive (TRANSVERSAL — arreglar todas, el Inbox está bug)
- [ ] 🔴 **Inbox mobile (BUG):** el layout 2-paneles (`360px + 1fr`) se rompe en mobile → colapsar a navegación lista→detalle (tap en conversación abre detalle full-screen + botón volver). La más crítica.
- [ ] Resumen/dashboard mobile: KPI cards + grid "Decisiones" apilan limpio.
- [ ] Recomendaciones mobile: cards destacadas/memos a una columna.
- [ ] Segmentos mobile: cards de sujetos a una columna + chips de filtro que wrappean.
- [ ] Canales mobile: filas/tabla de canales responsive.
- [ ] Equipo + Ajustes: pasada mobile.
- [ ] Masthead/nav global: colapsar la nav (hamburger o nav scrollable) en mobile.
- [ ] QA final a 375px (iPhone) en todas las páginas, especialmente el triage del Inbox.

---

## Frontend (setiq-web)

### Páginas que faltan construir
- [x] `/recomendaciones` — vista dedicada al feed completo de insights con filtro Todas/Resumen/Destacadas/Memos. Backend: `GET /insights?kind=&limit=&offset=`. (hecho 2026-05-20)
- [x] `/equipo` — admin de `tenant_users` (listar miembros + filtro por rol). Backend: `GET /team`. (hecho 2026-05-20)
- [x] `/ajustes` — editable: Kaizen module toggle, 4 toggles de Política de IA, 4 inputs de Etiquetas de canales (todo persistido vía `PATCH /tenants/me/settings|modules`). Identidad + cards `future` siguen read-only por diseño. (hecho 2026-06-03)

### Hacer la app interactiva
- [x] ~~Modal "+ Agregar sujeto" en `/segmentos`~~ — hecho 2026-06-03.
- [x] ~~Editar / pausar / eliminar segmentos desde la card~~ — hecho 2026-06-03 (kebab menu + confirm modal).
- [x] ~~**Competitor activity panel en `/overview`**~~ — hecho 2026-06-03 (Saul: `GET /dashboard/competitor-activity` + grid de top competidores con delta semanal en el dashboard).
- [x] ~~**Drill-down de competidor** en `/segmentos`~~ — hecho 2026-06-03 (Saul: drawer con menciones, sentiment, top contactos · backend `GET /tracked-subjects/{id}/detail`).
- [x] ~~Toggles de módulos en `/canales`~~ — hecho 2026-06-03 (Saul: `PATCH /channels/{key}` + toggles funcionales).
- [x] ~~Botón "Conectar canal" en `/canales`~~ — código hecho 2026-06-21 (Roger: handoff OAuth real vía `meta-oauth.service.ts` → `GET /auth/meta/connect` → Meta → `?meta_connected=N`). El OAuth real contra cuentas de clientes sigue bloqueado por App Review (en modo dev sólo funciona con Testers).
- [ ] Botón "Sincronizar todo" — dispara workers de Apify a demanda.
- [x] ~~Reasignar / marcar resuelto desde el inbox~~ — hecho 2026-06-03 (Saul: acciones por conversación · backend `PATCH /conversations/{id}` status + assignment).
- [x] ~~Responder al cliente desde el inbox~~ — código hecho 2026-06-21 (Roger: textarea + botón Enviar en el detalle del inbox → `POST /conversations/{id}/reply`). El envío real lo va a rechazar Meta hasta tener App Review (permisos write en Advanced Access) — el código está bien, sólo falta el review.

### Polish del dashboard / shell
- [x] ~~Wire del masthead a `/auth/me`~~ — hecho 2026-05-20 (MeService + tenant inline en /auth/me).
- [x] ~~Form de login real~~ — hecho 2026-05-20 (página `/login` con email + password + recordarme).
- [x] ~~Logout button + flujo de sesión expirada~~ — hecho 2026-05-20 (avatar dropdown + interceptor 401 → /login).
- [x] ~~Tenant switcher (cuando el user pertenezca a >1 tenant)~~ — hecho 2026-06-21 (Roger: switcher en el masthead · backend `GET /auth/me` lista membresías + `POST /auth/switch-tenant`).
- [x] ~~Búsqueda ⌘K~~ — hecho 2026-06-03 (Saul: palette sobre conversaciones / contactos / segmentos · backend `GET /search`).
- [x] ~~Filtros adicionales en el inbox (sentiment + canal combinados)~~ — hecho 2026-06-03 (chips client-side, componen entre sí, grupos vacíos se ocultan).
- [x] ~~Responsive / mobile~~ — hecho 2026-06-03 (Saul: breakpoints mobile/tablet).
- [x] ~~Empty states + error states consistentes~~ — hecho 2026-06-21 (Roger: `<app-empty-state>` wired en channels, inbox, equipo, ajustes, recomendaciones, segmentos — 5 páginas migradas + channels previo).

### Datos / demo
- [x] ~~Plantillas más variadas en seed~~ — hecho 2026-06-03 (30 → 75 plantillas; +9 mentions; +5 insights; timestamps de mentions sesgados a últimos 14 días para que el panel de competidores muestre data).
- [x] ~~Datos para `/recomendaciones`~~ — hecho 2026-06-03 (18 insights mix lead/featured/memo).

---

## Backend (setiq-api)

### Endpoints que faltan
- [x] ~~`GET /auth/me` debería devolver tenant info inline~~ — hecho 2026-05-20 (devuelve `{user, initials, role, tenant:{id,slug,name,modules}}`).
- [x] ~~`GET /insights` paginado~~ — hecho 2026-05-20 (Roger).
- [x] ~~`POST /team/invite`~~ — hecho 2026-06-03 (idempotente; devuelve temp_password sólo cuando crea usuario nuevo). `GET /team` ya existía.
- [x] ~~`PATCH /tenants/me/settings` y `PATCH /tenants/me/modules`~~ — hecho por Saul (en uso por `/ajustes` desde 2026-06-03).
- [x] ~~`PATCH /channels/{key}` (toggles de módulos)~~ — hecho 2026-06-03 (Saul).
- [x] ~~`GET /search?q=...`~~ — hecho 2026-06-03 (Saul, alimenta ⌘K).
- [x] ~~`GET /tenants/me`~~ — hecho 2026-06-03 (Roger, lo necesita `/ajustes` para hidratar estado).
- [x] ~~`PATCH /conversations/{id}`~~ — hecho 2026-06-03 (Saul: status + assignment).
- [x] ~~`POST /conversations/{id}/reply`~~ — código hecho 2026-06-21 (Roger: busca el page token, lo desencripta y llama al Graph API correcto según canal · `conversations/router.py:reply_to_conversation`). El send real lo rechaza Meta hasta App Review.
- [x] ~~`POST /auth/logout`~~ — hecho 2026-06-03 (Saul, con revocación de `jti`).
- [x] ~~`POST /auth/refresh`~~ — hecho 2026-06-03 (Saul).
- [x] ~~`GET /auth/me` lista membresías de tenant + `POST /auth/switch-tenant`~~ — hecho 2026-06-21 (Roger).

### Integración Meta (OAuth + webhooks)  *(código completo 2026-06-21 · Roger)*
- [x] ~~OAuth endpoints `GET /auth/meta/connect` · `GET /auth/meta/callback` · `POST /auth/meta/disconnect`~~ — `src/setiq/integrations/oauth.py`.
- [x] ~~Callbacks obligatorios de Meta: `POST /auth/meta/deauthorize` + `POST /auth/meta/data-deletion-callback`~~ — con verificación de `signed_request`.
- [x] ~~Cliente Graph API v22.0~~ — `src/setiq/integrations/meta.py`.
- [x] ~~Encriptación Fernet de page tokens en reposo~~ — `src/setiq/integrations/secrets.py` (prefijo `enc:v1:`; tokens viven en `tenants.settings.meta.connected_pages`).
- [x] ~~Verificación de firma HMAC-SHA256 de webhooks~~ — `src/setiq/ingestion/meta.py`.
- [x] ~~Crear/configurar la Meta App en el dashboard~~ — hecho 2026-06-23 (app Empresa `1728486774842629`, 3 casos de uso, OAuth redirect, webhooks IG+Messenger, permisos IG/FB habilitados, testers, URLs legales). Falta sólo **App Review** (bloqueado por incorporación de empresa).

### Workers / pipelines
- [ ] Worker Arq de Apify: dispara actors según `tracked_subjects` activos, persiste resultados en `mentions`. Bloqueado por cuenta Apify con saldo. **(ÚLTIMO — sólo TikTok/competidores, no bloquea el MVP)**
- [~] Worker Arq de clasificación — worker deployado 2026-06-23. Classifier ahora pluggable vía **LiteLLM** (`CLASSIFIER_MODEL`): sandbox `groq/moonshotai/kimi-k2-instruct` (gratis, needs `GROQ_API_KEY`), prod por cliente real `anthropic/claude-haiku-4-5` (needs `ANTHROPIC_API_KEY`). Switch = una env var, sin cambios de código. Se activa al agregar la key correspondiente.
- [ ] Postmark inbound (email ingestion). Necesita cuenta Postmark + DNS de Thalma.
- [ ] WhatsApp Business via Meta Cloud API. Bloqueado hasta App Review + cliente con número provisionado. **(NO CONSIDERAR TODAVÍA — fuera de alcance)**
- [x] ~~Cron de limpieza de `webhook_events` viejos (hard-delete > 30 días)~~ — hecho 2026-06-23 (`cleanup_webhook_events` como `cron_jobs` de Arq, diario 03:00 UTC). Worker Arq deployado en la VPS → el cron ya corre.

### Schema / datos
- [x] ~~Tabla `connected_channels` real (con tokens, last_sync_at, token_expires_at)~~ — hecho 2026-06-23 (migración `20260623210000_connected_channels.sql` con RLS; OAuth callback inserta ahí, deauthorize/data-deletion borra cross-tenant vía admin pool, disconnect borra scoped, reply lee el token desde la tabla). Los page tokens ya NO viven en `tenants.settings.meta.connected_pages`. `last_sync_at`/`token_expires_at` existen como columnas (aún sin poblar). El display de `/canales` sigue derivando estado demo de `settings.meta.page_ids` (separado, sin cambios).
- [x] ~~Soporte multi-página por tenant~~ — hecho 2026-06-23 (migración agrega `received_by_page_id` a `conversations`; el parser la setea con el page/IG id que recibió el evento; el reply elige el token exacto en `connected_channels` por `page_id` (FB) o `instagram_business_account->>'id'` (IG), con fallback a la heurística por canal).
- [ ] Plantillas semilla más diversas (alineado con el punto del frontend).
- [x] ~~TMR · Kaizen real~~ — hecho 2026-06-03 (LATERAL join sobre messages, WoW delta cuando hay cambio ≥ 1m; seed agrega outbound agent replies en ~60% de inbounds).
- [x] ~~Sin resolver — delta WoW real~~ — hecho 2026-06-03 (backlog actual vs hace 7d con heurística "último mensaje inbound"; `X altas` se movió a sub).

### Calidad
- [x] ~~Tests de integración para los endpoints~~ — hecho 2026-06-03 (Saul: suite de integración para auth/tenants/conversations/tracked-subjects).
- [x] ~~Ruff + mypy CI~~ — hecho 2026-06-03 (Saul, baseline green).
- [x] ~~Logging estructurado~~ — hecho 2026-06-03 (Saul: structlog wired).

---

## Infra / Ops

- [x] ~~Deploy en VPS con Docker Compose~~ — hecho 2026-06-23 en OVHcloud (no Hetzner): Postgres + Redis + FastAPI + web SSR + Caddy + worker Arq. Runbook en `deploy/README.md`.
- [ ] Backups de Postgres a Backblaze B2 (pgbackrest).
- [ ] Sentry / Logtail para errores.
- [x] ~~CI con GitHub Actions~~ — hecho 2026-06-23 (CI ruff/mypy/pytest + web build en PRs a main; CD deploy a la VPS en merge a main, ambos repos).
- [x] ~~Dominio + DNS~~ — hecho 2026-06-23: `setiq.lat` (landing Firebase) + `app.setiq.lat`/`api.setiq.lat` → VPS.
- [x] ~~Privacy Policy + Terms of Service + Data Deletion publicados~~ — hecho 2026-06-23: servidos públicamente en `https://app.setiq.lat/assets/legal/{privacy,terms,data-deletion}.html` (fix: `angular.json` no copiaba `src/assets`; ahora sí). Falta sólo reemplazar el placeholder `Roger Vaca` por la razón social cuando la empresa se incorpore.
- [x] ~~HTTPS + certs~~ — hecho 2026-06-23 (Caddy auto-TLS para api/app.setiq.lat).
- [ ] Variables de entorno separadas dev/staging/prod.

---

## CRM de ventas  *(diferido — siguiente versión del producto, NO MVP)*

**Qué es:** un pipeline de leads de venta + workflow de seguimiento por un agente comercial. **NO** es una vista unificada de contactos / interacciones (eso ya lo da el inbox + futura pantalla de contactos).

**Distinción crítica:** cuando ITALSA u otro cliente dice "necesitamos el CRM", se refiere a esto — capturar gente que mostró intención de compra y darle seguimiento hasta cerrar la venta. Los docs originales (SDD v1/v2, CONCEPTO) mezclan "CRM" con "contact master record" — confirmado con Roger 2026-05-20 que el alcance real es estrictamente sales-lead pipeline.

### Surfaces de captura de leads

- **Voice 0800** — transcripción de llamada entrante; si Claude detecta intención de compra, crea un lead.
- **WhatsApp opt-in** — un nuevo contacto que abre conversación por WA Business con palabras de intención ("quiero cotizar", "precios", etc.).
- **Click en CTA de post / ad social** — link "Contactar" o "Comprar" en publicaciones IG/FB → form embebido o redirect a WhatsApp con mensaje pre-llenado.
- **Formulario web embebible** — para que el tenant ponga "Quiero info" en su landing.

Cada lead capturado lleva: nombre (si lo hay), teléfono/email, canal de origen, post/ad/campaña disparadora, texto de intención, timestamp.

### Pipeline + workflow del agente comercial

- **Stages configurables por tenant** — default sugerido: Nuevo → Contactado → Calificado → Propuesta enviada → Ganado / Perdido.
- **Asignación a un usuario** (rol "sales agent" — nuevo, distinto de admin/agent/viewer actuales).
- **Recordatorios de follow-up** — "han pasado 48h sin contacto, recordá a María".
- **Log de actividad por lead** — llamadas, mensajes, notas libres.
- **Cierre** con motivo (ganado-precio-justo / perdido-fuera-de-presupuesto / perdido-otro-proveedor / etc.).

### Reporting

- Volumen de leads por fuente (qué post/ad/canal genera más).
- Conversion rate por stage (dónde se pierden).
- Performance por agente.
- Tiempo de primer contacto (KPI clásico de CRM de ventas).

### Fuera de alcance (aun en esta versión)

- Valores monetarios por oportunidad ($X esperado), forecasting.
- Vista kanban — empezar con tabla + filtros.
- Integración con ERP / facturación.
- Scoring predictivo de probabilidad de cierre.
- Auto-secuencias de email/WhatsApp (drip campaigns).

### Data model propuesto (cuando se desbloquee)

```
leads (
  id, tenant_id, contact_id (opcional, link a contacts si conocemos a la persona),
  source_channel, source_ref (id del post/ad/llamada),
  intent_text, name_hint, phone, email,
  stage_key (FK a lead_stages),
  assigned_user_id,
  captured_at, last_activity_at, closed_at, close_reason,
  ...
)

lead_stages (
  tenant_id, key, label, sort_order, is_won, is_lost
)

lead_activity (
  id, lead_id, kind (call/message/note/stage_change),
  body, by_user_id, occurred_at
)
```

### Pre-requisitos para arrancar

- [ ] MVP terminado y un cliente activo usándolo.
- [ ] Voice 0800 transcription funcionando (sino sólo capturamos por WA + social).
- [ ] WhatsApp Business API habilitado (no se puede sin App Review aprobado).
- [ ] Rol `sales_agent` agregado a `tenant_users`.

### Cuándo lo conversamos en serio

Cuando ITALSA (u otro cliente) firme contrato y diga explícitamente "necesitamos esto en V2". Mientras tanto, **no construir nada de esto** — incluso si parece tentador agregar tablas "por las dudas".

---

## Tenant context & taxonomías para IA  *(diferido — bloqueante cuando entre el segundo tenant)*

**El problema:** hoy todos los prompts que mandamos a Claude están hardcodeados asumiendo que el tenant es Thalma (periodista). Para ITALSA o cualquier cliente futuro, las categorías serían distintas (cliente fiel / distribuidor / queja por lote X vs. estudiante de periodismo / lectora habitual / crítico). La plataforma necesita **capturar el contexto del tenant** y usarlo en cada llamada a Claude — sin eso, no escala más allá del primer cliente.

### Data model propuesto

Agregar a `tenants.settings.context` (JSONB):

```json
{
  "about": "Texto libre que describe el negocio del tenant.",
  "industry": "journalism" | "consumer_goods" | "saas" | "influencer" | ...,
  "audience_categories": [
    { "key": "...", "label": "...", "description": "..." },
    ...
  ],
  "topic_categories": [
    { "key": "...", "label": "...", "description": "..." },
    ...
  ],
  "operational_alerts": [ "complaint cluster geográfico", "..." ]
}
```

### Surfaces de IA que tienen que leer este contexto

- **Bio enrichment de contactos** (Apify perfil + Claude tag) — usa `audience_categories`.
- **Clasificación de mensajes y mentions** — hoy intent fijo (`complaint/praise/question/...`). Debería extenderse con `topic_categories` del tenant.
- **Recommendation engine** — qué insights generar depende de `operational_alerts` y de la industria.
- **Memo generator** — el lenguaje de las memos también tiene que reflejar el contexto.

### Cómo capturarlo sin hacer que el tenant haga todo el trabajo

1. **Templates por industria** — al firmar, elegís "periodismo / consumer goods / SaaS / influencer / agencia / ..." y arrancás con un taxonomy default editable.
2. **Auto-sugerencia desde datos reales** — primera pasada sobre ~50 bios de gente que ya interactuó; Claude sugiere 5-7 categorías; el tenant aprueba.
3. **Free-form per tenant** — sólo un párrafo "about us" que se inyecta como contexto en cada prompt. Menos estructurado pero cero setup form.

Recomendación: combinar **1 + 2** (template + ajuste por datos reales) cuando esté el segundo tenant.

### Tareas concretas (cuando se desbloquee)

- [ ] Migración: agregar campo `tenants.settings.context` con el shape propuesto.
- [ ] Endpoint `PATCH /tenants/me/context` (parte de `/ajustes`).
- [ ] Refactor: cada prompt builder lee el contexto del tenant en vez de hardcodear categorías.
- [ ] Form de onboarding con templates por industria.
- [ ] Job de auto-sugerencia de taxonomy desde bios reales.
- [ ] Ablandar las memos hardcoded del seed para reflejar lo que la plataforma genuinamente puede medir hoy (sin enrichment de bios).

### Estado actual

- Para Thalma (único tenant) podemos **hardcodear el contexto en el seed o como constantes en código**. Cuesta cero hoy.
- Antes de onboardear un segundo cliente, esto deja de ser opcional.

---

## Bloqueos externos (no requieren código)

| Bloqueo | Quién resuelve | Tiempo |
|---|---|---|
| **Saldo en Anthropic API** | Roger — agregar US$5 a la cuenta cuando haya tarjeta con crédito | minutos |
| **Cuenta Apify + saldo** | Roger | minutos (US$5 alcanza para meses de test) |
| **Cuenta Postmark** (email inbound) | Roger | minutos |
| **Meta Business Manager de Thalma** + Business Verification | Thalma | 2-5 días |
| **Conectar IG Business + FB Page de Thalma a la Meta App** | Thalma (OAuth) | minutos una vez la app esté creada |
| **Crear Meta App nuestra** en developers.facebook.com | Roger | 1 hora |
| **App Review de Meta** | Roger submitte, Meta aprueba | 3-6 semanas |
| **Incorporación legal** (Unipersonal / SRL) en Bolivia | Roger + contador | 1-2 semanas (sólo cuando ITALSA esté cerca) |
| **Business Verification con NIT** ante Meta | Roger | 2-5 días después de incorporar |
| **Trámite WhatsApp Business** (número + templates) | Roger + ITALSA | 2-4 semanas, sólo cuando ITALSA firme |

> 📄 **Ver análisis completo:** [meta_permissions_read_vs_write.md](./meta_permissions_read_vs_write.md) — qué permisos pedimos, qué ayuda/perjudica la aprobación, timeline realista, tres caminos posibles, checklist de submission, y qué se le puede decir vs. no a un cliente sobre la capacidad de responder desde el inbox.

---

## Equipo / Proceso

- [x] ~~Invitar a Saul como colaborador en los repos~~ — hecho 2026-05-20: org `setiq-ai` creada, Saul agregado como Owner, repos transferidos.
- [ ] Asignar módulos a Saul cuando confirmemos qué área toma (backend / frontend / Apify).
- [ ] Onboardear a Thalma al Meta App como Tester (cuando esté creada la app).
- [ ] Lista de competidores / keywords / hashtags definitiva para Thalma (hoy hay valores plausibles en el seed).
- [ ] Definir el flujo de demos: a quién mostrar el MVP primero (ITALSA contacto, otros prospectos).

---

## Demo / Sales

- [ ] Video demo end-to-end de SETIQ contra la cuenta de Thalma (necesario para App Review).
- [ ] Actualizar el landing en `setiq-f8f84.web.app` para que coincida con la marca real (hoy quedó como ejemplo de "Decide rápido. Con inteligencia.").
- [ ] One-pager / pitch deck para clientes prospectivos.
- [ ] Pricing model (cuánto cobramos por tier — SETIQ core vs SETIQ + Kaizen).

---

## Notas de contexto

- **Schema actual:** 17 tablas, 5+ migraciones aplicadas. Multi-tenant con RLS desde día 1.
- **Repos:** `github.com/setiq-ai/setiq-api`, `github.com/setiq-ai/setiq-web` (ambos privados, commits firmados con SSH; org `setiq-ai` con Roger + Saul como Owners).
- **Stack confirmado:** FastAPI + asyncpg + dbmate + Arq · Angular 21 (SSR + hydration) + SCSS · sin Tailwind ni Material.
- **País:** Bolivia. NO usar referencias a Argentina (CUIT, CABA, Rosario, etc.) en seeds o copy.
- **Equipo:** Roger (backend lead), Saul (TBD), Thalma (piloto / co-fundadora / journalist).
- **Cliente objetivo:** ITALSA + clientes futuros. ITALSA tiene Kaizen activado; otros sólo SETIQ core.
- **Hoy todo corre en local.** Hetzner es el siguiente destino.
