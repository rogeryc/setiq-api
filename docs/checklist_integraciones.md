# Checklist de integraciones por canal

Trámites, credenciales y aprobaciones necesarias para cada canal que SETIQ / KAIZEN soporta. Casi todo el camino crítico **no es código** — es paperwork con plataformas. Por eso, para cada canal incluimos también la **alternativa Apify** (scraping marketplace) que evita aprobaciones a cambio de otros trade-offs.

Convenciones:
- **Calendario** = tiempo real-mundo, no horas de trabajo.
- **Costo** = recurrente mensual, salvo que se indique.
- **Camino oficial** = registrar nuestra app en el portal del desarrollador de la plataforma y pasar su proceso de aprobación.
- **Camino Apify** = consumir resultados desde [apify.com](https://apify.com) (actors pre-construidos que scrapean por nosotros).

---

## Familia Meta — Base común

Para cualquier integración oficial con WhatsApp, Instagram o Facebook, esto se hace **una vez por cliente** (no aplica si vamos por Apify):

1. **Crear Meta Business Manager** ([business.facebook.com](https://business.facebook.com)) si el cliente no lo tiene.
2. **Business Verification** — subir documentos legales (RUT/CUIT, dirección, sitio web). Tarda 2-5 días hábiles. Sin esto, ninguna integración oficial funciona.
3. **Facebook Page del cliente** vinculada al Business Manager.
4. **Cuenta de Instagram Business** linkeada a esa Facebook Page (si el cliente está en IG).
5. **Crear nuestra Meta App** ([developers.facebook.com](https://developers.facebook.com)) — una sola app cubre WhatsApp + IG + Messenger.
6. **Asignar la app al Business Manager del cliente**.

**Calendario base:** 1-2 semanas (mayormente esperando Business Verification del cliente).

---

## Modelo de aprobación Meta: una app nuestra, muchos clientes

Antes de entrar canal por canal: **nosotros registramos UNA Meta App, la pasamos por App Review una sola vez, y cada cliente se conecta a ella vía OAuth**. Los clientes nunca tocan el portal de desarrolladores de Meta. Es el mismo modelo que usan Hootsuite, Sprout Social, Manychat, Respond.io, Sprinklr — todos los SaaS que integran con Meta.

### Quién hace qué

| Tarea | Quién | Frecuencia |
|---|---|---|
| Registrar Meta App + pasarla por App Review | **Nosotros** | Una sola vez (cubre WhatsApp + IG + Messenger en la misma app) |
| Mantener Privacy Policy / Terms en URLs públicas | **Nosotros** | Continuo |
| Business Verification de nuestro Business Manager | **Nosotros** | Una vez |
| OAuth para conectar sus cuentas a nuestra app | **Cada cliente** | Una vez, click-through |
| Business Verification del cliente | **Cada cliente** | Una vez (2-5 días) |
| (Sólo WhatsApp) provisionar número + display name | **Cada cliente** | Una vez por número |

### ¿Es aprobable nuestro caso de uso?

Sí. "Plataforma de atención al cliente / engagement para empresas" es uno de los casos más aprobados por Meta — hay cientos de competidores ya aprobados (Hootsuite, Sprout, Manychat, Wati, Respond.io) haciendo exactamente lo mismo con los mismos permisos que necesitamos.

Lo que Meta evalúa en App Review:

- **Descripción del caso de uso** — explicar claramente que ayudamos a empresas a responder y analizar interacciones de sus propios clientes.
- **Video demo** end-to-end del flujo (a veces Meta también testea en vivo).
- **Privacy Policy + Terms of Service** en URLs públicas reales.
- **Retención y manejo de datos** explicado.
- **Permisos solicitados** — tienen que mapear al caso de uso, sin pedir de más.

### Calendario realista

**Budget 3-6 semanas** para la primera App Review, no 1-3:

- Meta suele pedir clarificaciones en round 1 ("mostrá esta pantalla específica en el demo").
- Algunos permisos (sobre todo WhatsApp) piden verificación adicional de **nuestro** business.
- Apps nuevas reciben más escrutinio que apps que ya pasaron una vez.

Después de la primera aprobación, **agregar nuevos clientes toma minutos** — sólo OAuth.

### Dos variantes que cambian la ecuación

1. **WhatsApp vía BSP** (Twilio, 360dialog, Wati) en vez de Meta Cloud API directo. El BSP ya hizo el trabajo pesado de aprobaciones; nos enchufamos a ellos. Trade-off: markup de ~10-30% sobre el precio de Meta por conversación, a cambio de **onboarding en días, no semanas**. Pura decisión de costo vs velocidad.
2. **Embedded Signup (white-label WhatsApp)** — Meta tiene un flow para partners aprobados que permite que cada cliente vea el onboarding de WhatsApp branded como nuestra plataforma. Más complejo de implementar; se difiere a feature premium.

### Resumen

- **Una Meta App nuestra → App Review una vez → todos los clientes se conectan vía OAuth.** Patrón estándar.
- **Aprobable:** sí, el caso de uso es de los más aprobados. 3-6 semanas la primera vez.
- **Por cliente:** sólo su propia Business Verification + click de OAuth.
- **Cuellos de botella críticos:** (a) nuestra primera App Review — bloqueante por calendario para todos los clientes, (b) Business Verification de cada cliente — no bloqueante entre clientes.

---

## WhatsApp Business

### Camino oficial — Meta Cloud API

**Lo que necesita el cliente:**
- Business Manager + Business Verification ✓
- **Número de teléfono dedicado**, no en uso en WhatsApp personal ni Business app (7 días de wait si recién se desregistró).
- Display name comercial aprobado por Meta.

**Lo que hacemos nosotros:**
- Agregar producto "WhatsApp" a nuestra Meta App.
- Crear WhatsApp Business Account (WABA) bajo el Business Manager del cliente.
- Registrar el número, configurar webhook (`POST /webhooks/whatsapp`), suscribirse a `messages` y `message_status`.
- Permisos: `whatsapp_business_messaging`, `whatsapp_business_management`.
- **App Review** + **message templates** aprobados (para mensajes proactivos fuera de la ventana 24h).

**Aprobaciones:** App Review 1-3 sem, display name 1-3 días, templates minutos a 24h.

**Calendario total:** 2-4 semanas.

**Costo:** gratis hasta 1000 conv. service/mes, luego ~US$0.005-0.08 por conv.

### Apify como alternativa

❌ **No es viable.** WhatsApp es end-to-end encrypted; los mensajes no existen en ninguna superficie pública. Apify no puede leerlos ni enviarlos. No hay atajo.

### Veredicto

**Camino oficial obligatorio.** Si el cliente quiere WhatsApp, tiene que pasar por Meta.

---

## Instagram — DMs

### Camino oficial — Instagram Messaging API

**Lo que necesita el cliente:** cuenta IG Business o Creator linkeada a una FB Page ✓.

**Lo que hacemos nosotros:**
- Producto "Instagram Graph API" en la app + permisos `instagram_basic`, `instagram_manage_messages`, `pages_show_list`.
- Webhook (`POST /webhooks/meta`) suscrito a IG events.
- OAuth flow para que el cliente conecte su cuenta.
- **App Review** con demo video.

**Calendario total:** 2-4 semanas. **Costo:** gratis.

### Apify como alternativa

❌ **No es viable.** DMs son privados, nunca aparecen en ninguna superficie scrapeable.

### Veredicto

**Camino oficial obligatorio.**

---

## Instagram — Comentarios en posts del cliente

### Camino oficial — Instagram Graph API

**Lo que necesita el cliente:** cuenta IG Business + acceso OAuth.

**Lo que hacemos nosotros:**
- Permiso `instagram_manage_comments` en la misma Meta App.
- Webhook suscrito a `comments` events sobre la cuenta IG del cliente.
- App Review (aprovecha la review compartida con DMs).

**Calendario:** 2-4 semanas (junto con IG DMs). **Costo:** gratis.

### Apify como alternativa

✅ **Viable.** Apify tiene actors como `apify/instagram-scraper` que leen posts públicos del perfil del cliente y sus comentarios sin pedir nada al cliente — sólo el username público.

**Lo que hacemos nosotros:**
- Cuenta Apify + API token.
- Job recurrente que dispara el actor cada N minutos sobre la lista de perfiles a monitorear.
- Consumir resultados vía webhook o polling.

**Calendario:** 1-2 días. **Costo:** ~US$2-5 por 1000 resultados.

### Comparación

| | Oficial | Apify |
|---|---|---|
| Setup | 2-4 semanas | 1-2 días |
| Costo | Gratis | ~US$2-5 / 1000 ítems |
| Latencia | Webhook real-time | Polling (minutos-horas) |
| Cliente debe conectar cuenta | Sí (OAuth) | No |
| Permite responder | ✅ | ❌ Sólo lectura |
| Legal | Limpio | Zona gris (vs ToS de Meta) |
| Estabilidad | Alta | Frágil (actors se rompen con cambios de Meta) |

**Veredicto:** Oficial si el cliente conecta su cuenta (recomendado por estabilidad + permite responder). Apify como fallback si el cliente no puede / no quiere conectar y sólo necesita lectura.

---

## Facebook — Messenger (DMs)

### Camino oficial

**Lo que necesita el cliente:** FB Page + admin nos da acceso.

**Lo que hacemos nosotros:**
- Permisos `pages_messaging`, `pages_show_list`.
- Webhook suscrito a Page event `messages`.
- App Review.

**Calendario:** 2-4 semanas. **Costo:** gratis.

### Apify como alternativa

❌ **No viable.** DMs privados.

### Veredicto

**Oficial obligatorio.**

---

## Facebook — Comentarios en Page del cliente

### Camino oficial

**Lo que necesita el cliente:** FB Page + admin nos da acceso.

**Lo que hacemos nosotros:**
- Permisos `pages_read_engagement`, `pages_manage_metadata`.
- Webhook suscrito a Page event `feed` (posts + comentarios).
- App Review (compartida con Messenger e IG).

**Calendario:** 2-4 semanas. **Costo:** gratis.

### Apify como alternativa

✅ **Viable.** Actors como `apify/facebook-posts-scraper` extraen posts y comentarios de Pages públicas.

**Setup:** 1-2 días. **Costo:** ~US$2-5 / 1000 ítems.

### Comparación

| | Oficial | Apify |
|---|---|---|
| Setup | 2-4 semanas | 1-2 días |
| Costo | Gratis | Pago por uso |
| Latencia | Real-time | Polling |
| Permite responder | ✅ | ❌ |
| Cliente debe conectar | Sí | No |
| Legal | Limpio | Zona gris |

**Veredicto:** mismo razonamiento que IG comments — oficial preferido, Apify como fallback de sólo-lectura.

---

## Email

**No aplica Apify** (no es red social). Dos opciones:

**Opción A — Postmark / SendGrid inbound parse (recomendado)**
- Cliente: control DNS de un subdominio.
- Nosotros: cuenta Postmark + inbound stream con webhook + cliente configura MX.
- Calendario: 1-2 días. Costo: ~US$15/mes hasta 10k emails.

**Opción B — IMAP de buzón existente**
- Cliente: credenciales IMAP/SMTP de su casilla (app password si tienen MFA).
- Nosotros: worker que pollea IMAP + outbound SMTP.
- Calendario: horas. Costo: ninguno extra.

Trade-off: IMAP es más simple pero frágil (tokens, MFA). Recomendado Postmark.

---

## 0800 / Teléfono

**No aplica Apify** (no es red social ni contenido scrapeable).

**Lo que necesita el cliente:** decisión migrar a Twilio o mantener existente.

**Lo que hacemos nosotros:**
- Twilio: comprar número (o port-in del existente) + Programmable Voice + grabación + transcripción (Whisper / AssemblyAI sobre el audio).

**Calendario:** número nuevo 1-2 días; port-in 2-6 semanas.

**Costo:** número ~US$1/mes; llamadas ~US$0.013/min entrante; transcripción ~US$0.006/min.

---

## TikTok

### Camino oficial

❌ **Inviable.** La TikTok Display API y Login Kit sólo permiten al creator linkeado leer su propio contenido publicado — no permite leer comentarios de la audiencia sobre un post del cliente en forma útil. No hay equivalente a Meta Messaging.

### Apify como alternativa (única opción)

✅ Apify es **la única vía realista**. Actors disponibles: `clockworks/tiktok-scraper`, `apidojo/tiktok-scraper`, `clockworks/tiktok-comments-scraper`. Leen posts de perfiles públicos + sus comentarios.

**Setup:** 1-2 días. **Costo:** pago por resultado.

### Veredicto

**Apify, o no soportar TikTok.** Aceptar trade-offs de polling + zona gris ToS. Como TikTok no permite responder DMs vía API públicamente, el caso de uso queda limitado a **lectura/análisis** — encaja en SETIQ core, no en KAIZEN.

---

## Resumen comparativo: oficial vs Apify por canal

| Canal | Oficial | Apify | Recomendado |
|---|---|---|---|
| **WhatsApp** | 2-4 sem aprobación; gratis-bajo | ❌ Inviable | Oficial |
| **Instagram DMs** | 2-4 sem; gratis | ❌ Inviable | Oficial |
| **Instagram comments** | 2-4 sem; gratis | 1-2 días; ~US$2-5/1000 | Oficial (Apify si cliente no conecta) |
| **Messenger DMs** | 2-4 sem; gratis | ❌ Inviable | Oficial |
| **FB Page comments** | 2-4 sem; gratis | 1-2 días; ~US$2-5/1000 | Oficial (Apify si cliente no conecta) |
| **TikTok** | ❌ Inviable | 1-2 días; pago x uso | Apify |
| **Email** | 1-2 días; ~US$15/mes | N/A | Postmark |
| **0800** | 1-2 días (nuevo) / 2-6 sem (port) | N/A | Twilio |

---

## Resumen ejecutivo por orden de implementación

| # | Canal | Vía | Calendario | Costo | Bloqueo crítico |
|---|---|---|---|---|---|
| 1 | **Email** (Postmark) | Postmark | 1-2 días | US$15/mes | DNS del cliente |
| 2 | **TikTok** | Apify | 1-2 días | Pago x uso | Ninguno |
| 3 | **IG / FB comments — fallback rápido** | Apify | 1-2 días | Pago x uso | Ninguno |
| 4 | **Meta Business base del cliente** | Oficial | 1-2 semanas | — | Business Verification |
| 5 | **IG DMs + Messenger DMs + comments oficiales** | Oficial | 2-4 semanas | Gratis | App Review |
| 6 | **WhatsApp Business** | Oficial | 2-4 semanas | ~US$0.005-0.08/conv | App Review + número + templates |
| 7 | **0800 nuevo** | Twilio | 1-2 días | ~US$1/mes + uso | Ninguno |
| 7b | **0800 port-in** | Twilio | 2-6 semanas | Idem | Trámite con carrier |

**Estrategia recomendada:**
1. **Días 1-7:** levantar (1)-(3) — todo lo que no requiere aprobaciones largas — para tener un MVP demostrable con varios canales funcionando.
2. **En paralelo desde día 1:** iniciar (4) y (6) para que las aprobaciones largas estén listas cuando el MVP base esté firme.
3. **Apify como fallback** para clientes que no pueden / no quieren conectar sus cuentas Meta — permite ofrecer lectura inmediata mientras se hace el trámite oficial.
