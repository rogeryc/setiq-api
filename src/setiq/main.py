from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from setiq import db, queue
from setiq.auth import router as auth_router
from setiq.channels import router as channels_router
from setiq.config import settings
from setiq.conversations import router as conversations_router
from setiq.dashboard import router as dashboard_router
from setiq.ingestion import meta_router
from setiq.insights import router as insights_router
from setiq.search import router as search_router
from setiq.team import router as team_router
from setiq.tenants import router as tenants_router
from setiq.tracked_subjects import router as tracked_subjects_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.connect()
    await queue.connect()
    try:
        yield
    finally:
        await queue.disconnect()
        await db.disconnect()


app = FastAPI(
    title="SETIQ API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tracked_subjects_router)
app.include_router(dashboard_router)
app.include_router(conversations_router)
app.include_router(channels_router)
app.include_router(insights_router)
app.include_router(search_router)
app.include_router(team_router)
app.include_router(tenants_router)
app.include_router(meta_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
async def ready() -> dict[str, str]:
    async with db.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ready"}
