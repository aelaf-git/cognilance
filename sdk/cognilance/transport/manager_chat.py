"""Lightweight chat server for CognilanceManager — no A2A or registry listing."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from cognilance.assets import ICON_PATH, LOGO_PATH

ManagerHandlerFn = Callable[[Any, str], Awaitable[str]]


class ManagerChatServer:
    """HTTP API for a manager script (no browser UI — use the Cognilance orchestrator chat)."""

    def __init__(
        self,
        *,
        manager: Any,
        handler: ManagerHandlerFn,
        description: str = "",
    ) -> None:
        self._manager = manager
        self._handler = handler
        self._description = description
        self.app = FastAPI(title=f"Manager — {manager.agent_name}")
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @self.app.get("/logo.png")
        async def logo() -> FileResponse:
            if not LOGO_PATH.is_file():
                raise HTTPException(status_code=404, detail="Logo not found")
            return FileResponse(LOGO_PATH, media_type="image/png")

        @self.app.get("/icon.png")
        async def icon() -> FileResponse:
            if not ICON_PATH.is_file():
                raise HTTPException(status_code=404, detail="Icon not found")
            return FileResponse(ICON_PATH, media_type="image/png")

        @self.app.post("/chat")
        async def chat_message(request: Request) -> JSONResponse:
            payload: dict[str, Any] = await request.json()
            text = str(payload.get("text", "")).strip()
            if not text:
                raise HTTPException(status_code=400, detail="text is required")
            try:
                reply = await self._dispatch(text)
                return JSONResponse(content={"text": reply})
            except Exception as exc:
                return JSONResponse(
                    status_code=500,
                    content={"text": str(exc), "error": True},
                )

        @self.app.get("/")
        async def root() -> dict[str, str]:
            return {"status": "ok", "health": "/health", "chat": "POST /chat"}

    async def _dispatch(self, message: str) -> str:
        if message.lower() == "agents":
            return await self._format_agents()
        return await self._handler(self._manager, message)

    async def _format_agents(self) -> str:
        agents = await self._manager.discover(limit=50)
        if not agents:
            return "No agents in the registry."
        lines = []
        for agent in agents:
            skills = ", ".join(s.name for s in agent.skills)
            lines.append(f"• {agent.name} [{skills}]")
        return "\n".join(lines)
