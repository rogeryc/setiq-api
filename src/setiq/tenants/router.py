from typing import Any

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, status

from setiq.auth.dependencies import CurrentUser, get_tenant_db, require_admin

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me")
async def get_me(
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        SELECT id, slug, name, modules, settings
        FROM tenants
        WHERE id = current_tenant_id()
        """
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return {
        "id": str(row["id"]),
        "slug": row["slug"],
        "name": row["name"],
        "modules": row["modules"],
        "settings": row["settings"],
    }


@router.patch("/me/settings")
async def patch_settings(
    patch: dict[str, Any] = Body(...),
    _admin: CurrentUser = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "settings must be an object")
    row = await conn.fetchrow(
        """
        UPDATE tenants
        SET settings = settings || $1::jsonb, updated_at = NOW()
        WHERE id = current_tenant_id()
        RETURNING settings
        """,
        patch,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return {"settings": row["settings"]}


@router.patch("/me/modules")
async def patch_modules(
    patch: dict[str, Any] = Body(...),
    _admin: CurrentUser = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "modules must be an object")
    row = await conn.fetchrow(
        """
        UPDATE tenants
        SET modules = modules || $1::jsonb, updated_at = NOW()
        WHERE id = current_tenant_id()
        RETURNING modules
        """,
        patch,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return {"modules": row["modules"]}
