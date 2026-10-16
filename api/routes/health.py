"""Health, agent listing, and static brand assets."""

from __future__ import annotations

from cognilance.assets import integration_logo_media_type, integration_logo_path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from agents.loader import SPECIALISTS
from api.deps import STATIC_DIR
from core.broker.policy import policy_snapshot
from pipelines import available_pipelines

router = APIRouter()


@router.get("/")
async def root() -> JSONResponse:
    return JSONResponse(content={"status": "ok", "health": "/health"})


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/skills/online")
async def skills_online() -> JSONResponse:
    """In-process specialist roles (no registry)."""
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
async def marketplace_agents_legacy() -> JSONResponse:
    """Legacy alias for /skills/online."""
    return await skills_online()


def _static_png(name: str) -> FileResponse:
    path = STATIC_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(path, media_type="image/png")


@router.get("/logo.png")
async def logo() -> FileResponse:
    return _static_png("logo.png")


@router.get("/icon.png")
async def icon() -> FileResponse:
    return _static_png("icon.png")


@router.get("/logo-light.png")
async def logo_light() -> FileResponse:
    return _static_png("logo-light.png")


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
