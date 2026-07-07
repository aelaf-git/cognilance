"""Request-scoped context for orchestrator graph execution."""

from __future__ import annotations

from contextvars import ContextVar

current_user_id: ContextVar[str] = ContextVar("current_user_id", default="default")
current_conversation_id: ContextVar[str] = ContextVar("current_conversation_id", default="")
current_mission_id: ContextVar[str] = ContextVar("current_mission_id", default="")
