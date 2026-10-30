"""FastAPI routers grouped by resource."""

from __future__ import annotations

from fastapi import APIRouter

from api.routes import chat, conversations, docx, health, integrations, runs, sessions

ALL_ROUTERS: tuple[APIRouter, ...] = (
    health.router,
    runs.router,
    integrations.router,
    conversations.router,
    sessions.router,
    chat.router,
    docx.router,
)

__all__ = ["ALL_ROUTERS"]
