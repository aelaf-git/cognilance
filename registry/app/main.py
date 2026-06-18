"""Cognilance Registry API — application entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.api import agents, health, traces
from app.config import get_settings
from app.dashboard import DASHBOARD_HTML
from app.database import connect_db, disconnect_db, prisma
from app.services.agents import mark_stale_agents_offline
from app.ws import TraceHub

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
LOGO_PATH = STATIC_DIR / "logo.png"


async def _stale_agent_loop() -> None:
    settings = get_settings()
    while True:
        try:
            count = await mark_stale_agents_offline(prisma)
            if count:
                logger.info("Marked %d stale agent(s) offline", count)
        except Exception:
            logger.exception("Stale agent check failed")
        await asyncio.sleep(settings.stale_check_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await connect_db()
    task = asyncio.create_task(_stale_agent_loop())
    logger.info("Registry API starting (heartbeat timeout: %ss)", settings.heartbeat_timeout_seconds)
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await disconnect_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Cognilance Registry",
        description="Production API for the Cognilance AI agent marketplace",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.trace_hub = TraceHub()

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if origins == ["*"] else origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(traces.router)

    @app.get("/logo.png")
    async def logo() -> FileResponse:
        if not LOGO_PATH.is_file():
            raise HTTPException(status_code=404, detail="Logo not found")
        return FileResponse(LOGO_PATH, media_type="image/png")

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DASHBOARD_HTML

    return app


app = create_app()


def cli() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    cli()
