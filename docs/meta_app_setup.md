# Meta App Setup — Handoff

Guía paso a paso para configurar la integración con Meta (Facebook +
Instagram) en SETIQ desde una Meta App ya existente.

Esto NO cubre la creación inicial de la app (que está en
`meta_permissions_read_vs_write.md`). Asume que ya tenés tu propia Meta App
o acceso a la nuestra y vas a conectarla a esta base de código.

**Última actualización:** 2026-06-07
**Lo que ya está implementado en el código:** todo el lado de SETIQ —
endpoints OAuth (`/auth/meta/connect|callback|disconnect`), callbacks
obligatorios (`/auth/meta/deauthorize`, `/auth/meta/data-deletion-callback`),
verificación de webhooks con HMAC-SHA256, cliente Graph API v22.0,
encriptación Fernet de page tokens, endpoint de reply
(`POST /conversations/{id}/reply`), botón "Conectar canal" en `/canales`,
páginas legales en `/assets/legal/{privacy,terms,data-deletion}.html`.

**Lo que falta del lado de Meta:** rellenar campos en el dashboard de
developers.facebook.com con los valores que se generan abajo + agregar a
los usuarios como Testers.

---

## 1. Permisos / casos de uso que la app necesita

SETIQ necesita 3 casos de uso. En `developers.facebook.com` → tu app →
sidebar izquierda **"Casos de uso"** / **"Use cases"**, agregá:

| Caso de uso | Para qué |
|---|---|
| **Administrar mensajes y contenido en Instagram** | Leer y responder comentarios + DMs de IG Business |
| **Administrar todos los aspectos de tu página** | Leer y responder comentarios + posts de páginas de FB |
| **Interactuar con los clientes en Messenger from Meta** | Enviar DMs vía Messenger |

Cuando los activás, Meta agrega automáticamente los permisos individuales
necesarios. La lista equivalente en scope strings (la usamos en el código
del OAuth):

```
pages_show_list
pages_read_engagement
pages_messaging
pages_messaging_subscriptions
pages_manage_engagement
pages_manage_metadata
instagram_basic
instagram_manage_comments
instagram_manage_messages
business_management
```

Estos permisos están hardcoded en `setiq-api/src/setiq/integrations/oauth.py`
como `OAUTH_SCOPES`. Si cambiás la lista en el dashboard, sincronizá ahí.

**Modo dev (Standard Access)** te alcanza hasta tener un cliente real listo.
Hasta entonces sólo los Testers (ver sección 5) pueden hacer OAuth contra
la app sin App Review aprobado.

---

## 2. URLs que hay que registrar en el dashboard

Antes de seguir necesitás:
- Una URL HTTPS pública apuntando a tu backend (`/auth/meta/*`,
  `/webhooks/meta`). En dev podés usar **ngrok** (ver sección 6). En prod
  será `https://api.setiq.bo` o similar.
- Una URL HTTPS pública apuntando a las páginas legales. Hoy las hostea
  el dev server en `/assets/legal/...`; eventualmente van al landing page.

Voy a usar como ejemplo `https://API` y `https://WEB` — reemplazá por
los valores reales que estés usando.

### 2.1 Privacy Policy URL, Terms of Service URL, Data Deletion URL

Dashboard → **Configuración → Básica** → buscar los tres campos:

| Campo | Valor |
|---|---|
| URL de la política de privacidad | `https://WEB/assets/legal/privacy.html` |
| Condiciones del servicio | `https://WEB/assets/legal/terms.html` |
| Instrucciones para la eliminación de datos del usuario | `https://WEB/assets/legal/data-deletion.html` |

Estas tres URLs son **obligatorias para App Review**. Si las páginas no
están publicadas todavía, Meta no te deja submitear. Las plantillas
están listas en `setiq-web/src/assets/legal/` — copiá-pegá los HTML
al landing y reemplazá el placeholder `Roger Vaca` con la razón social
cuando la empresa se incorpore.

### 2.2 Valid OAuth Redirect URI

Dashboard → **Facebook Login for Business** (puede que diga sólo
"Facebook Login") → **Configuración** → **URI de redireccionamiento de
OAuth válidos** → agregar:

```
https://API/auth/meta/callback
```

Tiene que coincidir **exacto** con el valor de la env var
`META_OAUTH_REDIRECT_URI` (ver sección 4). Si no coinciden char por
char, Meta rechaza el OAuth.

### 2.3 Webhook callback + Deauthorize callback + Data Deletion callback

Dashboard → **Productos** → **Webhooks** → **Configurar**.

Hay TRES URLs distintas que conviene registrar:

#### a) Callback URL principal (eventos)

| Campo | Valor |
|---|---|
| Callback URL | `https://API/webhooks/meta` |
| Verify Token | el valor de `META_WEBHOOK_VERIFY_TOKEN` de tu `.env` |

Al clickear "Verify and Save", Meta hace un GET con `hub.challenge=...`.
Nuestro endpoint (`src/setiq/ingestion/meta.py`) responde el challenge
si los verify tokens coinciden.

Después de verificar, suscribirse a los campos:
- **Para Instagram**: `comments`, `messages`, `message_reactions`
- **Para Page** (FB): `feed`, `messages`, `message_deliveries`, `message_reads`

#### b) Deauthorize Callback URL

Dashboard → **Configuración** → **Básica** → bajar a la sección de
**"Borrar"** o **"Avanzado"** → **URL de devolución de llamada de
desautorización**:

```
https://API/auth/meta/deauthorize
```

Esto se dispara cuando un usuario revoca SETIQ desde su FB settings.
Nuestro endpoint borra los tokens de las páginas que ese usuario había
autorizado.

#### c) Data Deletion Request URL

Mismo bloque, campo **"URL de la solicitud de eliminación de datos"**:

```
https://API/auth/meta/data-deletion-callback
```

Se dispara cuando el usuario pide eliminación explícita de sus datos
desde la configuración de privacidad de Facebook. Es similar al de
deauth pero distinto request, distinta semántica.

---

## 3. Claves que la app expone y que necesitamos

Después de configurar la app, copiá estos valores del dashboard:

### 3.1 App ID

Dashboard → **Configuración → Básica** → **"Id. de la app"** (16 dígitos).
Es público — no es secreto pero igual lo guardamos en `.env`.

### 3.2 App Secret

Dashboard → **Configuración → Básica** → **"Clave secreta de la app"**
→ click en **"Mostrar"** → te pide tu contraseña de Facebook → copiás.

**Tratá esto como una contraseña.** No lo committees, no lo pongas en
chat, no lo logues. Si se filtra, andá al mismo lugar y clickeá
**"Restablecer"** para rotarlo, después actualizá `.env`.

### 3.3 Verify Token (lo generás vos, no Meta)

Es una string aleatoria que vos elegís y que después configurás en el
dashboard de Meta cuando registrás el webhook (ver sección 2.3). Sirve
para confirmar que el que recibe el GET de Meta es tu backend y no un
random.

Para generar uno nuevo:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Te da algo como `N3NI-dK0GIHHOzjbDBEFeXZV5IysxaXGcMW5EY3KmXY`. Guardalo
en `.env` y usalo en el dashboard. Tiene que coincidir exacto.

### 3.4 Token Encryption Key (Fernet)

Es la clave simétrica con la que encriptamos los page tokens antes de
guardarlos en `tenants.settings.meta.connected_pages`. Si la rotás,
todos los tokens almacenados se invalidan y los usuarios tienen que
re-hacer OAuth.

Para generar:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Te da algo como `vBAiIEdJEQBiZl9dTeVs6_FTnKiSexVFmr46t_YOx54=`.

---

## 4. Wire en `.env` local

Después de tener los valores, abrí `setiq-api/.env` y completá esta
sección (las primeras dos vienen del dashboard, las otras dos las
generaste vos):

```bash
# Meta App credentials (developers.facebook.com)
META_APP_ID=<el App ID de 16 dígitos>
META_APP_SECRET=<el App Secret>
META_WEBHOOK_VERIFY_TOKEN=<lo que generaste con secrets.token_urlsafe(32)>
META_OAUTH_REDIRECT_URI=https://<tu-dominio-API>/auth/meta/callback
META_TOKEN_ENCRYPTION_KEY=<lo que generaste con Fernet.generate_key()>

# Origin del frontend (donde el callback redirige al usuario después de OAuth)
WEB_ORIGIN=http://localhost:4200   # en dev
# WEB_ORIGIN=https://app.setiq.bo  # en prod
```

`.env` está en `.gitignore` — no se committea. Para compartir cambios
de configuración, editá `.env.example` (sin valores reales).

Reiniciá el backend después de cambiar `.env` (uvicorn no recarga env
vars automáticamente, sólo cambios de código).

---

## 5. Agregar Testers / Developers

Mientras la app esté en modo dev (sin App Review aprobado), sólo los
usuarios que estén explícitamente listados como **Testers**, **Developers**
o **Administrators** pueden hacer OAuth contra ella.

Dashboard → **App Roles** / **Funciones de la app** → **Roles**.

| Rol | Cuándo |
|---|---|
| **Administrator** | Quienes pueden cambiar la configuración de la app (Roger, vos) |
| **Developer** | Quienes pueden hacer OAuth y ver logs (vos durante desarrollo) |
| **Tester** | Cuentas que vamos a usar para probar (Thalma, otras cuentas de prueba) |

Para agregar:
1. Click en **"Agregar"** → pegá el email de Facebook del usuario (ojo:
   el email asociado a su cuenta de FB, no el de trabajo).
2. El usuario recibe notificación en Facebook + email — tiene que **aceptar**
   para que la asignación se haga efectiva.

Cuentas para agregar como Tester:
- **Thalma** (cuenta de FB) — para que podamos hacer OAuth de sus páginas
- Cualquier otra cuenta de prueba que uses (la tuya, si querés probar
  con tu cuenta personal antes de meter a Thalma).

---

## 6. Probar localmente con ngrok

Meta sólo acepta URLs HTTPS públicas. Para dev sin deploy, usamos ngrok.

### Setup (una sola vez)

```bash
brew install ngrok
ngrok config add-authtoken <tu-token-de-ngrok.com>
```

Pedí un static domain en el dashboard de ngrok (free tier da uno) —
ej: `mi-setiq.ngrok-free.dev`. Sin static domain, el URL cambia cada
vez que reiniciás ngrok y tendrías que re-registrar en Meta. Con
static, queda fijo.

### Uso

Hay dos escenarios:

#### Escenario A: probar OAuth + Webhooks

ngrok apunta al backend (`:8000`). Las URLs de Meta usan este dominio.

```bash
ngrok http --domain=mi-setiq.ngrok-free.dev 8000
```

Y en `.env`:
```bash
META_OAUTH_REDIRECT_URI=https://mi-setiq.ngrok-free.dev/auth/meta/callback
```

(Más las URLs registradas en Meta dashboard apuntando al mismo dominio.)

#### Escenario B: mostrar la UI a alguien externo

ngrok apunta al frontend (`:4200`). El backend queda local; las
llamadas al API pasan por el dev-server proxy (ver `proxy.conf.json`).

```bash
ngrok http --domain=mi-setiq.ngrok-free.dev 4200
```

No podés hacer A y B con la misma cuenta de ngrok free (sólo 1 tunnel
simultáneo). Para hacer ambos en paralelo: pagar ngrok ($8/mo) o usar
dos dominios y arrancar dos sesiones.

### Verificar que el tunnel funciona

```bash
curl https://mi-setiq.ngrok-free.dev/health
# {"status":"ok","environment":"development"}

curl "https://mi-setiq.ngrok-free.dev/webhooks/meta?hub.mode=subscribe&hub.challenge=12345&hub.verify_token=<tu-verify-token>"
# 12345
```

Si el segundo te devuelve el challenge, el handshake con Meta va a
funcionar.

### Test harness offline (sin Meta)

Hay un script que simula webhooks de Meta firmados con tu App Secret y
los POSTea contra el backend local. Útil para validar el pipeline sin
involucrar a Meta:

```bash
cd setiq-api
.venv/bin/python -m scripts.test_meta_webhook
```

Manda los 4 tipos de evento (IG comment, IG DM, FB comment, FB Messenger)
+ un test de firma inválida. Reporta qué llega bien y qué falla.

---

## 7. Probar el OAuth real

Una vez que todo lo de arriba esté wired:

1. Asegurate de tener el backend corriendo (`uvicorn setiq.main:app`)
2. Asegurate de tener el frontend corriendo (`ng serve`)
3. Asegurate de tener ngrok arriba apuntando al API (escenario A)
4. Logueate en SETIQ como `thalma@example.com` / `changeme123`
5. Andá a `/canales`
6. Click en **"+ Conectar canal"**
7. El navegador te redirige a Meta — loguéate con la cuenta que agregaste
   como Tester (típicamente Thalma o tu cuenta personal con páginas)
8. Aceptá los permisos
9. Te tira de vuelta a `/canales?meta_connected=N`
10. Verificá en la DB:

```bash
psql -d setiq -c "SELECT settings -> 'meta' FROM tenants WHERE slug = 'thalma';"
```

Deberías ver un array `connected_pages` con N páginas, cada una con:
- `page_id`, `page_name`, `category`
- `page_token` empezando con `enc:v1:` (encriptado)
- `instagram_business_account` (si la página tiene IG linkeada)
- `connected_by_user_id` (el FB user ID de Thalma)

A partir de ahí, los webhooks de Meta empiezan a llegar (Meta los
suscribió automáticamente vía el código del callback) y vas a ver
eventos nuevos en `webhook_events` table.

### Probar reply

En `/inbox`, abrí una conversación, escribí algo en el textarea y
clickeá **Enviar**. El endpoint `POST /conversations/{id}/reply` busca
el page token, lo desencripta, y llama al Graph API correcto según el
canal.

**Heads up:** Meta probablemente va a rechazar el send hasta que tengamos
App Review aprobado (los permisos de write están en `Advanced Access`,
no en Standard). Esperá un error 502 con `Meta rechazó: permisos no aprobados`.
Eso es esperable y CORRECTO — el código está bien, sólo falta el review.

---

## 8. Pendientes / known limitations

Cosas que ya están en el código pero que vale la pena saber:

### 8.1 Page tokens en `tenants.settings.meta.connected_pages`

Hoy los tokens viven como JSONB dentro de `tenants.settings`. Funciona
pero idealmente moverían a una tabla `connected_channels` con schema
explícito. Está en TODO. El cambio es contenido: una migración + ajustar
el OAuth callback + ajustar la heurística de `_pick_connected_page` en
`conversations/router.py`.

### 8.2 Multi-page tenants

Si un tenant conecta más de una página, hoy `_pick_connected_page` toma
la primera (o la primera con IG link para canales de IG). Cuando un
tenant tenga varias páginas reales, necesitamos:
- Agregar columna `received_by_page_id` a `conversations`
- Que el parser de webhooks la setee al recibir el evento
- Que el reply endpoint la use para elegir el token correcto

### 8.3 App Review

Para usar la app con clientes reales (no testers), tenés que submitearla
a App Review. Pre-requisitos (en `meta_permissions_read_vs_write.md`):
- Empresa incorporada + Business Verification
- Privacy Policy, Terms, Data Deletion (URLs estables, lo cubrimos arriba)
- Demo video end-to-end mostrando el inbox + responder
- Justificación escrita por permiso

Tiempo total realista: 6-10 semanas.

### 8.4 WhatsApp Business

Está fuera del scope actual. La integración requiere su propia App Review,
provisión de número por cliente y templates de mensaje aprobados. No
tocamos esto hasta que un cliente lo pida explícitamente.

---

## 9. Archivos relevantes en el código

| Función | Archivo |
|---|---|
| OAuth endpoints | `setiq-api/src/setiq/integrations/oauth.py` |
| Graph API client | `setiq-api/src/setiq/integrations/meta.py` |
| Encriptación de tokens | `setiq-api/src/setiq/integrations/secrets.py` |
| Webhook ingestion + signature verify | `setiq-api/src/setiq/ingestion/meta.py` |
| Parser de payloads → DB | `setiq-api/src/setiq/ingestion/parser.py` |
| Test harness de webhooks | `setiq-api/scripts/test_meta_webhook.py` |
| Reply endpoint | `setiq-api/src/setiq/conversations/router.py` (búsqueda: `reply_to_conversation`) |
| Config / env vars | `setiq-api/src/setiq/config.py` |
| Botón "Conectar canal" + banner post-OAuth | `setiq-web/src/app/pages/channels/channels.page.{ts,html}` |
| Servicio OAuth frontend | `setiq-web/src/app/core/api/meta-oauth.service.ts` |
| Páginas legales | `setiq-web/src/assets/legal/{privacy,terms,data-deletion}.html` |

---

## 10. Resumen ejecutivo (TL;DR)

Si querés saltearte la lectura:

1. **En tu Meta App (developers.facebook.com)**:
   - Activar 3 casos de uso (IG mensajes/contenido, Pages, Messenger)
   - Agregar Privacy/Terms/Data-Deletion URLs en Configuración Básica
   - Registrar `https://<API>/auth/meta/callback` en Facebook Login → OAuth Redirect URIs
   - Registrar `https://<API>/webhooks/meta` en Webhooks + verify token
   - Registrar `https://<API>/auth/meta/deauthorize` en Configuración → Avanzado
   - Registrar `https://<API>/auth/meta/data-deletion-callback` ídem
   - Agregar testers (Thalma + vos)

2. **En `setiq-api/.env`**:
   - `META_APP_ID` (del dashboard)
   - `META_APP_SECRET` (del dashboard, click "Mostrar")
   - `META_WEBHOOK_VERIFY_TOKEN` (lo generás con `secrets.token_urlsafe(32)`)
   - `META_OAUTH_REDIRECT_URI` (debe coincidir exacto con lo que pusiste en Meta)
   - `META_TOKEN_ENCRYPTION_KEY` (lo generás con `Fernet.generate_key()`)

3. **Probar**:
   - `ngrok http --domain=... 8000` (tunnel HTTPS al backend)
   - Login en `/canales` → "+ Conectar canal" → seguir el OAuth
   - Verificar `tenants.settings.meta.connected_pages` en la DB
   - Mensajes nuevos deberían empezar a entrar al inbox

Cualquier error específico → revisar `setiq-api/src/setiq/integrations/oauth.py`
y los logs del backend.
