"""CognilanceAgent and TaskContext — the agent runtime."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import uvicorn

from cognilance.config import HEARTBEAT_INTERVAL_SECONDS, Config
from cognilance.core.models import (
    AgentCard,
    AgentVisibility,
    Skill,
    Task,
    TaskResult,
    TaskState,
)
from cognilance.registry.client import RegistryClient
from cognilance.transport.a2a import A2AClient, A2AServer

logger = logging.getLogger(__name__)

TaskHandlerFn = Callable[[Task, "TaskContext"], Awaitable[Task]]


class TaskContext:
    """Context passed to every task handler — discover and hire other agents."""

    def __init__(
        self,
        *,
        registry: RegistryClient,
        a2a: A2AClient,
        self_agent_id: str | None,
        api_key: str | None,
    ) -> None:
        self._registry = registry
        self._a2a = a2a
        self._self_agent_id = self_agent_id
        self._api_key = api_key

    async def discover(
        self,
        *,
        skills: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[AgentCard]:
        return await self._registry.discover(
            skills=skills,
            tags=tags,
            limit=limit,
            exclude_id=self._self_agent_id,
        )

    async def hire(
        self,
        agent: AgentCard,
        *,
        input_text: str = "",
        input_data: dict[str, Any] | None = None,
    ) -> TaskResult:
        result = await self._a2a.send_task(
            agent.url,
            input_text=input_text,
            input_data=input_data,
        )
        if result.status.state == TaskState.FAILED:
            raise RuntimeError(
                f"Agent {agent.name} failed: {result.status.message or 'unknown error'}"
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
        agents = await self.discover(skills=skills, tags=tags, limit=limit)

        if agents:
            return await self.hire(agents[0], input_text=input_text)

        if fallback_fn is None:
            raise RuntimeError(f"No agents found with skills {skills} and no fallback provided")

        result = fallback_fn(input_text)
        if asyncio.iscoroutine(result):
            return await result
        return result


class CognilanceAgent:
    """Build, register, and run an agent on the Cognilance platform."""

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
        self._handler: TaskHandlerFn | None = None
        self._agent_id: str | None = None
        self._agent_card: AgentCard | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None

    def on_task(self, fn: TaskHandlerFn) -> TaskHandlerFn:
        """Decorator to register the task handler."""
        self._handler = fn
        return fn

    def _build_agent_card(self, url: str) -> AgentCard:
        return AgentCard(
            id=self._agent_id,
            name=self.name,
            description=self.description,
            url=url,
            version=self.version,
            skills=[Skill.from_name(s) for s in self.skill_names],
            visibility=self.visibility,
            tags=self.tags,
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

    async def _handle_task(self, task: Task) -> Task:
        if not self._handler:
            return task.fail(message="No task handler registered. Use @agent.on_task.")

        registry = RegistryClient(
            registry_url=self._config.registry_url,
            api_key=self._config.require_api_key(),
        )
        a2a = A2AClient(api_key=self._config.api_key)
        ctx = TaskContext(
            registry=registry,
            a2a=a2a,
            self_agent_id=self._agent_id,
            api_key=self._config.api_key,
        )

        try:
            task.status.state = TaskState.WORKING
            result = await self._handler(task, ctx)
            if result.output is None and result.status.state == TaskState.WORKING:
                return result.complete(text="")
            return result
        finally:
            await registry.close()
            await a2a.close()

    def run(self, *, register: bool = True) -> None:
        """Start the A2A listener, register with the registry, and serve tasks."""
        if not self._handler:
            raise RuntimeError("No task handler registered. Decorate a function with @agent.on_task")

        api_key = self._config.require_api_key()
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

            registry = RegistryClient(
                registry_url=self._config.registry_url,
                api_key=api_key,
            )
            try:
                card = await registry.register(
                    name=self.name,
                    url=agent_url,
                    skills=self.skill_names,
                    description=self.description,
                    visibility=self.visibility,
                    tags=self.tags,
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
                    "For local dev, set COGNILANCE_REGISTRY_URL=http://127.0.0.1:8080 "
                    "(auto-started by `cognilance run`), start `cognilance registry` manually, "
                    "or use `--no-register`."
                ) from exc
            except Exception:
                await registry.close()
                raise

        logger.info("Starting %s on %s:%d", self.name, self.host, self._port)
        uvicorn.run(server.app, host=self.host, port=self._port)

    async def register_external(self, url: str) -> AgentCard:
        """Register an externally-hosted agent with the registry."""
        registry = RegistryClient(
            registry_url=self._config.registry_url,
            api_key=self._config.require_api_key(),
        )
        try:
            card = await registry.register(
                name=self.name,
                url=url,
                skills=self.skill_names,
                description=self.description,
                visibility=self.visibility,
                tags=self.tags,
            )
            self._agent_id = card.id
            return card
        finally:
            await registry.close()

    def _get_public_host(self) -> str:
        if self.host not in ("0.0.0.0", "::"):
            return self.host
        return "localhost"
