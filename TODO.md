# SETIQ — TODO

Lista de tareas pendientes en ambos repos + cosas externas (papeleo, cuentas).
Actualizar al final de cada sesión.

**Última actualización:** 2026-06-03 (sentiment+links en panel competidores, seed +variedad, empty-state share, filtros inbox)

---

## Prioridad actual (2026-05-28 · Saul)

- **Hacer ahora:** todo lo que NO esté bloqueado por cuentas externas — endpoints de escritura del backend, interactividad del frontend, y calidad (tests/CI/logging).
- **Apify → al final:** sólo aporta data de TikTok + competidores; no bloquea el resto del MVP.
- **WhatsApp → no considerar todavía:** depende de App Review + cliente con número; fuera de alcance por ahora.
- **Hecho 2026-05-28 (branch `saul`):** el parser de webhooks ya maneja las 4 superficies de Meta — IG comments + IG DMs, FB comments + FB Messenger (`src/setiq/ingestion/parser.py`). Antes sólo parseaba IG comments.

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
- [ ] Botón "Conectar canal" en `/canales` — abre flujo OAuth real (bloqueado por App Review de Meta).
- [ ] Botón "Sincronizar todo" — dispara workers de Apify a demanda.
- [x] ~~Reasignar / marcar resuelto desde el inbox~~ — hecho 2026-06-03 (Saul: acciones por conversación · backend `PATCH /conversations/{id}` status + assignment). Responder al cliente sigue diferido (espera App Review).

### Polish del dashboard / shell
- [x] ~~Wire del masthead a `/auth/me`~~ — hecho 2026-05-20 (MeService + tenant inline en /auth/me).
- [x] ~~Form de login real~~ — hecho 2026-05-20 (página `/login` con email + password + recordarme).
- [x] ~~Logout button + flujo de sesión expirada~~ — hecho 2026-05-20 (avatar dropdown + interceptor 401 → /login).
- [ ] Tenant switcher (cuando el user pertenezca a >1 tenant).
- [x] ~~Búsqueda ⌘K~~ — hecho 2026-06-03 (Saul: palette sobre conversaciones / contactos / segmentos · backend `GET /search`).
- [x] ~~Filtros adicionales en el inbox (sentiment + canal combinados)~~ — hecho 2026-06-03 (chips client-side, componen entre sí, grupos vacíos se ocultan).
- [x] ~~Responsive / mobile~~ — hecho 2026-06-03 (Saul: breakpoints mobile/tablet).
- [~] Empty states + error states consistentes — componente `<app-empty-state>` creado y wired en channels + inbox (los huecos críticos). Resto de páginas tienen UI local que funciona; migrarlas al componente cuando convenga.

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
- [ ] `POST /conversations/{id}/reply` (Kaizen — diferido a propósito, requiere App Review).
- [x] ~~`POST /auth/logout`~~ — hecho 2026-06-03 (Saul, con revocación de `jti`).
- [x] ~~`POST /auth/refresh`~~ — hecho 2026-06-03 (Saul).

### Workers / pipelines
- [ ] Worker Arq de Apify: dispara actors según `tracked_subjects` activos, persiste resultados en `mentions`. Bloqueado por cuenta Apify con saldo. **(ÚLTIMO — sólo TikTok/competidores, no bloquea el MVP)**
- [ ] Worker Arq de clasificación con Claude. Código listo (`setiq.workers.runner`); bloqueado por `ANTHROPIC_API_KEY` con saldo.
- [ ] Postmark inbound (email ingestion). Necesita cuenta Postmark + DNS de Thalma.
- [ ] WhatsApp Business via Meta Cloud API. Bloqueado hasta App Review + cliente con número provisionado. **(NO CONSIDERAR TODAVÍA — fuera de alcance)**
- [ ] Cron de limpieza de `webhook_events` viejos (hard-delete > 30 días).

### Schema / datos
- [ ] Tabla `connected_channels` real (con tokens, last_sync_at, token_expires_at) — hoy se deriva de `tenants.settings`. Funciona para demo, no escala.
- [ ] Plantillas semilla más diversas (alineado con el punto del frontend).
- [ ] Deltas reales para TMR · Kaizen y Sin resolver (hoy hardcodeados). Necesita ingestar mensajes outbound + timestamps de resolución.

### Calidad
- [x] ~~Tests de integración para los endpoints~~ — hecho 2026-06-03 (Saul: suite de integración para auth/tenants/conversations/tracked-subjects).
- [x] ~~Ruff + mypy CI~~ — hecho 2026-06-03 (Saul, baseline green).
- [x] ~~Logging estructurado~~ — hecho 2026-06-03 (Saul: structlog wired).

---

## Infra / Ops

- [ ] Deploy en Hetzner — 1 VPS con Docker Compose (Postgres, Redis, FastAPI, Arq worker, Caddy/Traefik).
- [ ] Backups de Postgres a Backblaze B2 (pgbackrest).
- [ ] Sentry / Logtail para errores.
- [ ] CI con GitHub Actions: lint + tests + build per push.
- [ ] Dominio + DNS (`setiq.bo`? `setiq.app`?).
- [ ] Privacy Policy + Terms of Service en URLs públicas (requisito de Meta App Review).
- [ ] HTTPS + certs (Caddy lo hace solo).
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
