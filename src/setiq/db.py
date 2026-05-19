import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from setiq.config import settings

_pool: asyncpg.Pool | None = None
_admin_pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register JSON codecs so jsonb columns round-trip as Python dicts/lists
    without manual json.dumps / json.loads at call sites."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def connect() -> None:
    global _pool, _admin_pool
    _pool = await asyncpg.create_pool(
        settings.app_database_url,
        init=_init_connection,
        min_size=2,
        max_size=10,
    )
    # Smaller pool used by background workers that need to read/write across
    # tenants (e.g. webhook parser). Connects as the superuser, so RLS is
    # bypassed. Worker code is still expected to set tenant_id explicitly on
    # inserts; RLS bypass is just to read webhook_events rows that have NULL
    # tenant_id and to write across tenants without per-tenant context flips.
    _admin_pool = await asyncpg.create_pool(
        settings.database_url,
        init=_init_connection,
        min_size=1,
        max_size=4,
    )


async def disconnect() -> None:
    global _pool, _admin_pool
    if _pool is not None:
        await _pool.close()
        _pool = None
    if _admin_pool is not None:
        await _admin_pool.close()
        _admin_pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pool


def admin_pool() -> asyncpg.Pool:
    if _admin_pool is None:
        raise RuntimeError("Admin pool not initialized")
    return _admin_pool


@asynccontextmanager
async def acquire() -> AsyncIterator[asyncpg.Connection]:
    async with pool().acquire() as conn:
        yield conn


@asynccontextmanager
async def admin_acquire() -> AsyncIterator[asyncpg.Connection]:
    async with admin_pool().acquire() as conn:
        yield conn


@asynccontextmanager
async def acquire_for_tenant(tenant_id: str) -> AsyncIterator[asyncpg.Connection]:
    """Acquire a connection inside a transaction with `app.current_tenant` set,
    so RLS policies on tenant-scoped tables enforce isolation for the duration
    of the request."""
    async with pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.current_tenant', $1, true)",
                tenant_id,
            )
            yield conn
