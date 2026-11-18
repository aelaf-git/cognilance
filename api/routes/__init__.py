"""FastAPI routers grouped by resource."""

from __future__ import annotations

from fastapi import APIRouter

from api.routes import (
    auth,
    chat,
    conversations,
    docx,
    health,
    integrations,
    organizations,
    projects,
    runs,
    sessions,
)

ALL_ROUTERS: tuple[APIRouter, ...] = (
    health.router,
    auth.router,
    runs.router,
    integrations.router,
    conversations.router,
    organizations.router,
    projects.router,
    sessions.router,
    chat.router,
    docx.router,
)

__all__ = ["ALL_ROUTERS"]
