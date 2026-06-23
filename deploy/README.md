# SETIQ — Deploy (OVHcloud VPS)

Production-ish deploy for the MVP / demo / Meta App Review environment.

## Box
- OVHcloud VPS-1, Ubuntu 26.04, 2 vCPU / 4GB + 2GB swap, Beauharnois (CA).
- IPv4: `149.56.44.13`
- SSH: key-only (`~/.ssh/setiq_vps`), user `ubuntu` (passwordless sudo).
- Firewall (ufw): 22, 80, 443 only.

## Domains (DNS A records → VPS)
- `api.setiq.lat` → backend (FastAPI)
- `app.setiq.lat` → frontend (Angular SSR)
- `setiq.lat` / `www` → Firebase landing (NOT this box)

HTTPS is auto-issued by Caddy (Let's Encrypt).

## Layout on server (`/home/ubuntu/setiq`)
```
docker-compose.yml      # postgres, redis, api, web, caddy
.env                    # secrets (chmod 600, NOT in git)
deploy/Caddyfile        # TLS + routing
setiq-api/              # rsynced from local saul branch
setiq-web/              # rsynced (has Dockerfile + .dockerignore)
```

Caddy routes API path prefixes on `app.setiq.lat` to the api container (mirrors the
dev `proxy.conf.json`), so the frontend's relative URLs (`API_BASE=''`) work unchanged.

## Services
`docker compose ps` — postgres, redis, api, web, caddy. Worker is intentionally
NOT run (needs `ANTHROPIC_API_KEY`; the demo uses pre-seeded classifications).

## Redeploy after code changes
From local repo root:
```
rsync -az --delete -e 'ssh -i ~/.ssh/setiq_vps' \
  --exclude node_modules --exclude .venv --exclude .git --exclude dist --exclude .angular \
  setiq-api/ ubuntu@149.56.44.13:/home/ubuntu/setiq/setiq-api/
# (repeat for setiq-web/)
ssh -i ~/.ssh/setiq_vps ubuntu@149.56.44.13 'cd setiq && docker compose build && docker compose up -d'
```

## Migrations (dbmate, run from server)
```
cd /home/ubuntu/setiq && source .env
docker run --rm --network setiq_default -v /home/ubuntu/setiq/setiq-api/dbmate:/db \
  -e DATABASE_URL="$DATABASE_URL" -e DBMATE_MIGRATIONS_DIR=/db/migrations \
  -e DBMATE_SCHEMA_FILE=/db/schema.sql ghcr.io/amacneil/dbmate:2 up
```

## Seed (Roger's local demo)
```
cd /home/ubuntu/setiq
for s in seed_dev seed_dev_sample seed_andina_sample; do
  docker compose run --rm --no-deps -w /app -v /home/ubuntu/setiq/setiq-api:/app api python scripts/$s.py
done
```
Logins: `thalma@example.com` / `changeme123` (admin of both tenants),
`demo@andina.example.com` / `changeme123`.

## Fill Meta + Anthropic creds later
Edit `/home/ubuntu/setiq/.env` → set `META_APP_ID`, `META_APP_SECRET`
(and `ANTHROPIC_API_KEY` when funded), then `docker compose up -d api`.
`META_WEBHOOK_VERIFY_TOKEN` and `META_TOKEN_ENCRYPTION_KEY` are already generated.

Meta dashboard URLs to register (see `setiq-api/docs/meta_app_setup.md`):
- OAuth redirect: `https://api.setiq.lat/auth/meta/callback`
- Webhook: `https://api.setiq.lat/webhooks/meta`
- Deauthorize: `https://api.setiq.lat/auth/meta/deauthorize`
- Data deletion: `https://api.setiq.lat/auth/meta/data-deletion-callback`
- Legal: `https://app.setiq.lat/assets/legal/{privacy,terms,data-deletion}.html`
