"""A2A send/receive — the inter-agent layer."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from cognilance.assets import LOGO_PATH
from cognilance.core.models import AgentCard, Task, TaskResult, TaskState
from cognilance.ui.dev_chat import agent_chat_html


class A2AError(Exception):
    """Raised when an A2A operation fails."""


TaskHandler = Callable[[Task], Awaitable[Task]]


class A2AServer:
    """HTTP server exposing A2A endpoints for an agent."""

    def __init__(
        self,
        *,
        agent_card: AgentCard,
        task_handler: TaskHandler,
    ) -> None:
        self._agent_card = agent_card
        self._task_handler = task_handler
        self._tasks: dict[str, Task] = {}
        self.app = FastAPI(title=f"A2A — {agent_card.name}")
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.get("/a2a")
        async def get_agent_card() -> dict[str, Any]:
            return self._agent_card.to_a2a_dict()

        @self.app.post("/a2a/tasks")
        async def create_task(request: Request) -> JSONResponse:
            payload = await request.json()
            task = Task.from_a2a_payload(payload)
            self._tasks[task.id] = task

            try:
                result = await self._task_handler(task)
                self._tasks[task.id] = result
                return JSONResponse(content=result.to_a2a_dict())
            except Exception as exc:
                failed = task.fail(message=str(exc))
                self._tasks[task.id] = failed
                return JSONResponse(
                    status_code=500,
                    content=failed.to_a2a_dict(),
                )

        @self.app.get("/a2a/tasks/{task_id}")
        async def get_task(task_id: str) -> dict[str, Any]:
            task = self._tasks.get(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return task.to_a2a_dict()

        @self.app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @self.app.get("/logo.png")
        async def logo() -> FileResponse:
            if not LOGO_PATH.is_file():
                raise HTTPException(status_code=404, detail="Logo not found")
            return FileResponse(LOGO_PATH, media_type="image/png")

        def _chat_page() -> str:
            tags = [t.lower() for t in self._agent_card.tags]
            if "delegator" in tags:
                role = "delegator"
            elif "worker" in tags:
                role = "worker"
            else:
                role = "agent"
            return agent_chat_html(
                name=self._agent_card.name,
                description=self._agent_card.description,
                skills=[s.name for s in self._agent_card.skills],
                role=role,
            )

        @self.app.get("/chat", response_class=HTMLResponse)
        async def chat() -> str:
            """Built-in chat UI shipped with the Cognilance SDK."""
            return _chat_page()

        @self.app.get("/dev/chat")
        async def dev_chat_redirect() -> RedirectResponse:
            return RedirectResponse(url="/chat", status_code=307)

        @self.app.get("/")
        async def root() -> RedirectResponse:
            return RedirectResponse(url="/chat", status_code=307)


class A2AClient:
    """Client for sending tasks to other agents via A2A."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            headers={"Content-Type": "application/json"},
            timeout=120.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_agent_card(self, agent_url: str) -> dict[str, Any]:
        url = f"{agent_url.rstrip('/')}/a2a"
        response = await self._client.get(url)
        if response.status_code >= 400:
            raise A2AError(f"Failed to fetch agent card from {url}: {response.text}")
        return response.json()

    async def send_task(
        self,
        agent_url: str,
        *,
        input_text: str = "",
        input_data: dict[str, Any] | None = None,
        trace: dict[str, Any] | None = None,
        poll_interval: float = 0.5,
        max_polls: int = 240,
    ) -> TaskResult:
        base = agent_url.rstrip("/")
        payload: dict[str, Any] = {
            "input": {
                "text": input_text,
                "data": input_data or {},
            }
        }
        if trace:
            payload["trace"] = trace

        response = await self._client.post(f"{base}/a2a/tasks", json=payload)
        if response.status_code >= 400:
            raise A2AError(f"Failed to send task to {base}: {response.text}")

        result_data = response.json()
        task_id = result_data.get("id")
        state = result_data.get("status", {}).get("state")

        if state in (TaskState.COMPLETED.value, TaskState.FAILED.value):
            return TaskResult.from_a2a_payload(result_data)

        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)
            poll_response = await self._client.get(f"{base}/a2a/tasks/{task_id}")
            if poll_response.status_code >= 400:
                raise A2AError(f"Failed to poll task {task_id}: {poll_response.text}")

            result_data = poll_response.json()
            state = result_data.get("status", {}).get("state")
            if state in (TaskState.COMPLETED.value, TaskState.FAILED.value):
                return TaskResult.from_a2a_payload(result_data)

        raise A2AError(f"Task {task_id} timed out waiting for completion")
