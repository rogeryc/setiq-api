from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from setiq import db
from setiq.auth import router as auth_router
from setiq.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.connect()
    try:
        yield
    finally:
        await db.disconnect()


app = FastAPI(
    title="SETIQ API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
async def ready() -> dict[str, str]:
    async with db.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ready"}
