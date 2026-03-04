"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI

from rp_engine import __version__
from rp_engine.config import get_config
from rp_engine.container import ServiceContainer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    config = get_config()

    services = await ServiceContainer.build(config)
    await services.start()
    app.state.services = services

    # Individual attrs for backward compatibility with dependencies.py
    for field in ServiceContainer.__dataclass_fields__:
        setattr(app.state, field, getattr(services, field))

    yield

    await services.close()


app = FastAPI(
    title="RP Engine",
    description="REST API for managing roleplay sessions",
    version=__version__,
    lifespan=lifespan,
)

# CORS — configurable origins (defaults to localhost only)
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_config().server.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from rp_engine.routers import (  # noqa: E402
    analyze,
    branches,
    cards,
    config,
    context,
    custom_state,
    exchanges,
    npc,
    rp,
    sessions,
    state,
    threads,
    timeline,
    triggers,
    vectors,
    writing,
)

app.include_router(cards.router)
app.include_router(sessions.router)
app.include_router(exchanges.router)
app.include_router(rp.router)
app.include_router(context.router)
app.include_router(triggers.router)
app.include_router(npc.router)
app.include_router(state.router)
app.include_router(threads.router)
app.include_router(analyze.router)
app.include_router(branches.router)
app.include_router(writing.router)
app.include_router(config.router)
app.include_router(vectors.router)
app.include_router(timeline.router)
app.include_router(custom_state.router)


@app.get("/health")
async def health_check():
    config = get_config()
    db = app.state.db if hasattr(app.state, "db") else None
    db_health = await db.health() if db else {"status": "not_initialized"}

    # Add indexed card count
    indexed = None
    if db:
        indexed = await db.fetch_val("SELECT COUNT(*) FROM story_cards")

    return {
        "status": "ok",
        "version": __version__,
        "vault_root": str(config.paths.vault_root),
        "database": db_health,
        "indexed_cards": indexed,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# Serve frontend static build (must be AFTER all API routes)
from fastapi.staticfiles import StaticFiles as _StaticFiles  # noqa: E402

_FRONTEND_BUILD = Path(__file__).parent.parent / "frontend" / "build"
if _FRONTEND_BUILD.exists():
    app.mount("/", _StaticFiles(directory=_FRONTEND_BUILD, html=True), name="frontend")
