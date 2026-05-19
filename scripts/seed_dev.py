"""Seed minimal dev data so the API has something to authenticate against.

Creates:
  - tenant `thalma` with SETIQ + KAIZEN modules enabled
  - user `thalma@example.com` with password `changeme123`
  - membership: thalma user is admin of thalma tenant

Idempotent: safe to re-run. Existing rows are not overwritten (so the password
hash stays stable across runs).

Usage:
  uv run python scripts/seed_dev.py
"""
import asyncio
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from setiq.auth.passwords import hash_password  # noqa: E402
from setiq.config import settings  # noqa: E402


async def main() -> None:
    # Use the superuser URL so RLS doesn't block inserts.
    conn = await asyncpg.connect(settings.database_url)
    try:
        async with conn.transaction():
            tenant_id = await conn.fetchval(
                """
                INSERT INTO tenants (slug, name, status, modules, settings)
                VALUES (
                    'thalma',
                    'Thalma',
                    'active',
                    '{"setiq": {"tier": "pro"}, "kaizen": {"enabled": true}}'::jsonb,
                    '{
                        "meta": {
                            "page_ids": ["100000000000001"],
                            "instagram_business_ids": ["17841400000000000"]
                        },
                        "tiktok": {"handle": "@thalma.periodista"},
                        "email":  {"address": "hola@thalma.bo"},
                        "channel_labels": {
                            "instagram": "@thalma.bo",
                            "facebook":  "Thalma · Página",
                            "tiktok":    "@thalma.periodista",
                            "email":     "hola@thalma.bo"
                        }
                    }'::jsonb
                )
                ON CONFLICT (slug) DO UPDATE SET
                    name     = EXCLUDED.name,
                    modules  = EXCLUDED.modules,
                    settings = EXCLUDED.settings
                RETURNING id
                """
            )
            print(f"tenant thalma → {tenant_id}")

            existing = await conn.fetchval(
                "SELECT id FROM users WHERE email = $1",
                "thalma@example.com",
            )
            if existing is None:
                user_id = await conn.fetchval(
                    """
                    INSERT INTO users (email, password_hash, name)
                    VALUES ($1, $2, 'Thalma')
                    RETURNING id
                    """,
                    "thalma@example.com",
                    hash_password("changeme123"),
                )
                print(f"user thalma@example.com → {user_id} (password: changeme123)")
            else:
                user_id = existing
                print(f"user thalma@example.com → {user_id} (already exists, password unchanged)")

            await conn.execute(
                """
                INSERT INTO tenant_users (tenant_id, user_id, role)
                VALUES ($1, $2, 'admin')
                ON CONFLICT (tenant_id, user_id) DO NOTHING
                """,
                tenant_id,
                user_id,
            )
            print("membership: thalma is admin of thalma tenant")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
