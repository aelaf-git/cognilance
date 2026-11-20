"""Health, agent listing, and static brand assets."""

from __future__ import annotations

import sqlite3

from cognilance.assets import integration_logo_media_type, integration_logo_path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from agents.loader import SPECIALISTS
from api.deps import STATIC_DIR, active_organization_id, org_store
from core.broker.policy import policy_snapshot
from core.context.db import ensure_db_dir
from core.runtime.checkpointer import checkpoint_db_path
from core.runtime.runs.store import RunStore
from pipelines import available_pipelines
from workers.schedulers.ticker import last_success_at

FAILED_WINDOW_SECONDS = 3600

router = APIRouter()


@router.get("/")
async def root() -> JSONResponse:
    return JSONResponse(content={"status": "ok", "health": "/health"})


def _reachable(path: str) -> bool:
    try:
        connection = sqlite3.connect(path)
    except sqlite3.Error:
        return False
    try:
        connection.execute("SELECT 1")
    except sqlite3.Error:
        return False
    finally:
        connection.close()
    return True


@router.get("/health")
async def health() -> JSONResponse:
    sqlite_ok = _reachable(str(ensure_db_dir()))
    checkpointer_ok = _reachable(checkpoint_db_path())
    failed_runs = 0
    if sqlite_ok:
        try:
            failed_runs = RunStore().count_failed(within_seconds=FAILED_WINDOW_SECONDS)
        except sqlite3.Error:
            sqlite_ok = False
    status = "ok" if sqlite_ok and checkpointer_ok else "failed"
    body = {
        "status": status,
        "sqlite": "ok" if sqlite_ok else "failed",
        "checkpointer": "ok" if checkpointer_ok else "failed",
        "ticker_at": last_success_at(),
        "failed_runs": failed_runs,
        "failed_window_seconds": FAILED_WINDOW_SECONDS,
    }
    if status != "ok":
        return JSONResponse(status_code=503, content=body)
    return JSONResponse(content=body)


@router.get("/skills/online")
async def skills_online(request: Request) -> JSONResponse:
    """In-process specialist roles, hiding agents this caller's organization disabled."""
    user_id = getattr(request.state, "user_id", None) or ""
    disabled: set[str] = set()
    if user_id:
        organization_id = active_organization_id(str(user_id))
        if organization_id:
            disabled = org_store.disabled_agent_ids(organization_id)
    rows = [
        {
            "id": role.id,
            "name": role.name,
            "online": True,
            "skills": list(role.skills),
            "tools": list(role.tools),
            "url": None,
            "description": role.description or role.instructions,
        }
        for role in SPECIALISTS
        if role.id not in disabled
    ]
    return JSONResponse(
        content={
            "agents": rows,
            "total": len(rows),
            "pipelines": available_pipelines(),
            "policy": policy_snapshot(),
        }
    )


@router.get("/marketplace/agents")
async def marketplace_agents_legacy(request: Request) -> JSONResponse:
    """Legacy alias for /skills/online."""
    return await skills_online(request)


def _static_png(name: str) -> FileResponse:
    path = STATIC_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(path, media_type="image/png")


@router.get("/icon.png")
async def icon() -> FileResponse:
    return _static_png("icon.png")


@router.get("/icon-light.png")
async def icon_light() -> FileResponse:
    return _static_png("icon-light.png")


@router.get("/integrations/logos/{integration_id}")
async def integration_logo(integration_id: str) -> FileResponse:
    """Serve brand logos for OAuth integrations (from cognilance/assets/integrations)."""
    path = integration_logo_path(integration_id.strip().lower())
    if path is None:
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(path, media_type=integration_logo_media_type(path))
