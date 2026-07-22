"""CognilanceWorker — marketplace agent that registers and serves A2A tasks."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

import httpx
import uvicorn

from cognilance.config import HEARTBEAT_INTERVAL_SECONDS, Config
from cognilance.core.models import (
    AgentCard,
    AgentVisibility,
    Skill,
    Task,
    TaskInput,
    TaskState,
)
from cognilance.core.tracing import TraceEmitter
from cognilance.registry.client import RegistryClient
from cognilance.transport.a2a import A2AServer

logger = logging.getLogger(__name__)

WorkerHandlerFn = Callable[[Task], Awaitable[Task]]


class _CognilanceRuntime(ABC):
    """Shared A2A server, registry registration, and heartbeats."""

    _role: str = ""

    def __init__(
        self,
        *,
        name: str,
        skills: list[str],
        description: str = "",
        tags: list[str] | None = None,
        visibility: AgentVisibility | str = AgentVisibility.PUBLIC,
        version: str = "0.1.0",
        host: str = "0.0.0.0",
        port: int | None = None,
        config: Config | None = None,
    ) -> None:
        self.name = name
        self.skill_names = skills
        self.description = description
        self.tags = tags or []
        self.visibility = (
            AgentVisibility(visibility) if isinstance(visibility, str) else visibility
        )
        self.version = version
        self.host = host
        self._config = config or Config.from_env(port=port)
        self._port = port or self._config.port
        self._agent_id: str | None = None
        self._agent_card: AgentCard | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._emitter: TraceEmitter | None = None

    @abstractmethod
    async def _run_handler(self, task: Task) -> Task:
        ...

    def _get_emitter(self) -> TraceEmitter:
        if self._emitter is None:
            self._emitter = TraceEmitter(registry_url=self._config.registry_url)
        return self._emitter

    async def _emit(self, task: Task, type: str, text: str = "", **data) -> None:
        await self._get_emitter().emit(
            trace_id=task.trace.trace_id,
            task_id=task.id,
            parent_task_id=task.trace.parent_task_id,
            depth=task.trace.depth,
            agent_name=self.name,
            type=type,
            text=text,
            data=data,
        )

    async def _handle_task(self, task: Task) -> Task:
        task._emitter = self._get_emitter()
        task._agent_name = self.name
        await self._emit(task, "task_received", text=task.input.text)

        task.status.state = TaskState.WORKING
        try:
            result = await self._run_handler(task)
        except Exception as exc:
            await self._emit(task, "task_failed", text=str(exc))
            raise

        result = self._finalize_result(task, result)
        if result.status.state == TaskState.FAILED:
            await self._emit(task, "task_failed", text=result.status.message or "failed")
        else:
            await self._emit(
                task,
                "task_completed",
                text=result.output.text if result.output else "",
            )
        return result

    def _registration_tags(self) -> list[str]:
        tags = list(self.tags)
        if self._role and self._role not in tags:
            tags.append(self._role)
        return tags

    def _build_agent_card(self, url: str) -> AgentCard:
        return AgentCard(
            id=self._agent_id,
            name=self.name,
            description=self.description,
            url=url,
            version=self.version,
            skills=[Skill.from_name(s) for s in self.skill_names],
            visibility=self.visibility,
            tags=self._registration_tags(),
        )

    async def _heartbeat_loop(self, registry: RegistryClient) -> None:
        while True:
            try:
                if self._agent_id:
                    await registry.heartbeat(self._agent_id)
                    logger.debug("Heartbeat sent for %s", self._agent_id)
            except Exception:
                logger.warning("Heartbeat failed", exc_info=True)
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

    def run(self, *, register: bool = True) -> None:
        """Start the A2A listener, register with the registry, and serve tasks."""
        agent_url = f"http://{self._get_public_host()}:{self._port}"
        self._agent_card = self._build_agent_card(agent_url)

        server = A2AServer(
            agent_card=self._agent_card,
            task_handler=self._handle_task,
        )

        @server.app.on_event("startup")
        async def on_startup() -> None:
            if not register:
                return

            registry = RegistryClient(registry_url=self._config.registry_url)
            try:
                card = await registry.register(
                    name=self.name,
                    url=agent_url,
                    skills=self.skill_names,
                    description=self.description,
                    visibility=self.visibility,
                    tags=self._registration_tags(),
                )
                self._agent_id = card.id
                self._agent_card.id = card.id
                server._agent_card = self._agent_card
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(registry))
                logger.info("Registered as %s at %s", self._agent_id, agent_url)
            except httpx.ConnectError as exc:
                await registry.close()
                raise RuntimeError(
                    f"Cannot reach registry at {self._config.registry_url}. "
                    "Start the registry (`cd registry && docker compose up`) "
                    "or set COGNILANCE_REGISTRY_URL to your hosted registry. "
                    "Use `--no-register` to skip registration."
                ) from exc
            except Exception:
                await registry.close()
                raise

        chat_url = f"http://{self._get_public_host()}:{self._port}/chat"
        logger.info("Starting %s on %s:%d (chat: %s)", self.name, self.host, self._port, chat_url)
        uvicorn.run(server.app, host=self.host, port=self._port)

    def chat(self, *, register: bool = True, open_ui: bool = False) -> None:
        """Start the A2A server, dev chat UI, and an interactive CLI prompt loop."""
        import webbrowser

        thread = threading.Thread(
            target=lambda: self.run(register=register),
            daemon=True,
            name=f"cognilance-{self.name}",
        )
        thread.start()

        health_url = f"http://127.0.0.1:{self._port}/health"
        for _ in range(60):
            try:
                if httpx.get(health_url, timeout=0.5).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            raise RuntimeError(f"{self.name} failed to start on port {self._port}")

        time.sleep(1.5)  # allow registry registration to finish

        chat_url = f"http://127.0.0.1:{self._port}/chat"

        print(f"\n{self.name} is live on port {self._port}")
        print(f"Chat UI: {chat_url}")
        print("Terminal below — or use the chat UI in your browser. Commands: 'agents', 'exit'.\n")

        if open_ui:
            webbrowser.open(chat_url)

        while True:
            try:
                prompt = input(f"{self.name}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not prompt or prompt.lower() in {"exit", "quit"}:
                break

            if prompt.lower() == "agents":
                asyncio.run(self._print_registry())
                continue

            task = Task(input=TaskInput(text=prompt))
            try:
                result = asyncio.run(self._handle_task(task))
            except Exception as exc:
                print(f"\nError: {exc}\n")
                continue

            if result.output:
                print(f"\n{result.output.text}\n")
                if result.output.data.get("hired"):
                    print(f"  ↳ hired: {result.output.data['hired']}\n")
            elif result.status.message:
                print(f"\nError: {result.status.message}\n")

    async def _print_registry(self) -> None:
        registry = RegistryClient(registry_url=self._config.registry_url)
        try:
            agents = await registry.discover(limit=50, exclude_id=self._agent_id)
            if not agents:
                print("\nNo agents in registry.\n")
                return
            print()
            for a in agents:
                skills = ", ".join(s.name for s in a.skills)
                print(f"  • {a.name} ({skills}) — {a.url}")
            print()
        finally:
            await registry.close()

    async def register_external(self, url: str) -> AgentCard:
        """Register an externally-hosted agent with the registry."""
        registry = RegistryClient(registry_url=self._config.registry_url)
        try:
            card = await registry.register(
                name=self.name,
                url=url,
                skills=self.skill_names,
                description=self.description,
                visibility=self.visibility,
                tags=self._registration_tags(),
            )
            self._agent_id = card.id
            return card
        finally:
            await registry.close()

    def _get_public_host(self) -> str:
        if self.host not in ("0.0.0.0", "::"):
            return self.host
        return "localhost"

    def _finalize_result(self, task: Task, result: Task) -> Task:
        if result.output is None and result.status.state == TaskState.WORKING:
            return result.complete(text="")
        return result


class CognilanceWorker(_CognilanceRuntime):
    """
    Worker — registers on the marketplace and delivers work when hired.
    """

    _role = "worker"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._handler: WorkerHandlerFn | None = None

    def on_task(self, fn: WorkerHandlerFn) -> WorkerHandlerFn:
        """Decorator to register the task handler: `async def handle(task)`."""
        self._handler = fn
        return fn

    async def _run_handler(self, task: Task) -> Task:
        if not self._handler:
            return task.fail(message="No task handler registered. Use @worker.on_task.")
        return await self._handler(task)

    def run(self, *, register: bool = True) -> None:
        if not self._handler:
            raise RuntimeError(
                "No task handler registered. Decorate a function with @worker.on_task"
            )
        super().run(register=register)
