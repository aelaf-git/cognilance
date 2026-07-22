"""CognilanceManager — discover and hire agents from any framework."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import uvicorn

from cognilance.config import Config, DEFAULT_PORT
from cognilance.core.models import AgentCard, AgentVisibility, TaskResult, TaskState, TraceContext
from cognilance.core.tracing import TraceEmitter
from cognilance.registry.client import RegistryClient
from cognilance.transport.a2a import A2AClient


class CognilanceManager:
    """
    Hire and discover agents on the Cognilance marketplace.

    Drop this into any existing project — LangChain, CrewAI, FastAPI, a script.
    No server or registry listing required. Use CognilanceWorker when you also want to be hired.

        async with CognilanceManager.from_env() as manager:
            agents = await manager.discover(skills=["translation"])
            result = await manager.hire(agents[0], input_text="Hello")
    """

    def __init__(
        self,
        *,
        registry_url: str | None = None,
        agent_id: str | None = None,
        config: Config | None = None,
        trace: TraceContext | None = None,
        task_id: str | None = None,
        agent_name: str = "Manager",
    ) -> None:
        cfg = config or Config.from_env()
        self._registry_url = (registry_url or cfg.registry_url).rstrip("/")
        self._agent_id = agent_id
        self._registry = RegistryClient(registry_url=self._registry_url)
        self._a2a = A2AClient()
        # Trace context: inherited when nested inside another hire chain,
        # otherwise this manager is the root of a new hire chain.
        self._trace = trace or TraceContext()
        self._task_id = task_id or f"manager-{uuid.uuid4().hex[:12]}"
        self._agent_name = agent_name
        self._emitter = TraceEmitter(registry_url=self._registry_url)

    @classmethod
    def from_env(
        cls,
        *,
        agent_id: str | None = None,
    ) -> CognilanceManager:
        """Create a manager using COGNILANCE_REGISTRY_URL from .env."""
        return cls(agent_id=agent_id)

    async def close(self) -> None:
        await self._registry.close()
        await self._a2a.close()
        await self._emitter.close()

    async def __aenter__(self) -> CognilanceManager:
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    @property
    def trace_id(self) -> str:
        """ID correlating every event in this hire chain (visible on the dashboard)."""
        return self._trace.trace_id

    @property
    def agent_name(self) -> str:
        return self._agent_name

    async def _emit(self, type: str, text: str = "", **data: Any) -> None:
        await self._emitter.emit(
            trace_id=self._trace.trace_id,
            task_id=self._task_id,
            parent_task_id=self._trace.parent_task_id,
            depth=self._trace.depth,
            agent_name=self._agent_name,
            type=type,
            text=text,
            data=data,
        )

    async def discover(
        self,
        *,
        skills: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[AgentCard]:
        """Search the registry for agents with matching skills."""
        agents = await self._registry.discover(
            skills=skills,
            tags=tags,
            limit=limit,
            exclude_id=self._agent_id,
        )
        await self._emit(
            "discover",
            text=f"Searched marketplace (skills={skills or 'any'}) — {len(agents)} found",
            skills=skills or [],
            tags=tags or [],
            found=len(agents),
            names=[a.name for a in agents],
        )
        return agents

    async def hire(
        self,
        agent: AgentCard,
        *,
        input_text: str = "",
        input_data: dict[str, Any] | None = None,
    ) -> TaskResult:
        """Send a task to another agent and await the result."""
        child_trace = self._trace.child(self._task_id)

        await self._emit(
            "hire_started",
            text=f"Hiring {agent.name}",
            agent=agent.name,
            agent_url=agent.url,
            input_text=input_text,
        )
        started = time.monotonic()
        try:
            result = await self._a2a.send_task(
                agent.url,
                input_text=input_text,
                input_data=input_data,
                trace=child_trace.model_dump(),
            )
        except Exception as exc:
            await self._emit(
                "hire_failed",
                text=f"{agent.name} unreachable: {exc}",
                agent=agent.name,
            )
            raise
        duration_ms = int((time.monotonic() - started) * 1000)
        if result.status.state == TaskState.FAILED:
            await self._emit(
                "hire_failed",
                text=f"{agent.name} failed: {result.status.message or 'unknown error'}",
                agent=agent.name,
                duration_ms=duration_ms,
            )
            raise RuntimeError(
                f"Agent {agent.name} failed: {result.status.message or 'unknown error'}"
            )
        await self._emit(
            "hire_completed",
            text=f"{agent.name} delivered in {duration_ms / 1000:.1f}s",
            agent=agent.name,
            duration_ms=duration_ms,
            output_text=result.output.text,
        )
        return result

    async def discover_and_hire(
        self,
        *,
        skills: list[str],
        input_text: str,
        fallback_fn: Callable[[str], str] | Callable[[str], Awaitable[str]] | None = None,
        tags: list[str] | None = None,
        limit: int = 5,
    ) -> TaskResult | str:
        """Find the best matching agent and hire them, or run a local fallback."""
        agents = await self.discover(skills=skills, tags=tags, limit=limit)
        if agents:
            return await self.hire(agents[0], input_text=input_text)
        if fallback_fn is None:
            raise RuntimeError(f"No agents found with skills {skills}")
        result = fallback_fn(input_text)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def register(
        self,
        *,
        name: str,
        url: str,
        skills: list[str],
        description: str = "",
        visibility: AgentVisibility | str = AgentVisibility.PUBLIC,
        tags: list[str] | None = None,
    ) -> AgentCard:
        """List your agent on the marketplace (you still need a server at `url`)."""
        vis = AgentVisibility(visibility) if isinstance(visibility, str) else visibility
        card = await self._registry.register(
            name=name,
            url=url,
            skills=skills,
            description=description,
            visibility=vis,
            tags=tags or [],
        )
        self._agent_id = card.id
        return card

    async def get_agent(self, agent_id: str) -> AgentCard:
        """Look up a single agent by ID."""
        return await self._registry.get_agent(agent_id)

    def chat(
        self,
        handler: Callable[[CognilanceManager, str], Awaitable[str]],
        *,
        description: str = "",
        host: str = "0.0.0.0",
        port: int | None = None,
        open_ui: bool = False,
    ) -> None:
        """
        Start a local chat UI and optional terminal loop.

        Managers are not listed on the registry — this only serves GET/POST /chat
        on the given port. Pass an async handler: ``async def handle(manager, message) -> str``.
        """
        import threading
        import time
        import webbrowser

        from cognilance.transport.manager_chat import ManagerChatServer

        listen_port = port or DEFAULT_PORT
        server = ManagerChatServer(
            manager=self,
            handler=handler,
            description=description,
        )

        thread = threading.Thread(
            target=lambda: uvicorn.run(server.app, host=host, port=listen_port),
            daemon=True,
            name=f"cognilance-manager-{self._agent_name}",
        )
        thread.start()

        health_url = f"http://127.0.0.1:{listen_port}/health"
        for _ in range(60):
            try:
                if httpx.get(health_url, timeout=0.5).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            raise RuntimeError(f"{self._agent_name} failed to start on port {listen_port}")

        chat_url = f"http://127.0.0.1:{listen_port}/chat"
        print(f"\n{self._agent_name} chat UI: {chat_url}")
        print("Terminal below — or use the chat UI in your browser. Commands: agents, exit.\n")

        if open_ui:
            webbrowser.open(chat_url)

        while True:
            try:
                line = input(f"{self._agent_name}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                break
            try:
                reply = asyncio.run(server._dispatch(line))
                print(f"\n{reply}\n")
            except Exception as exc:
                print(f"Error: {exc}\n")
