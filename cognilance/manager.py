"""CognilanceManager — discover and hire agents from any framework."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from cognilance.config import Config
from cognilance.core.models import AgentCard, AgentVisibility, TaskResult, TaskState
from cognilance.registry.client import RegistryClient
from cognilance.transport.a2a import A2AClient


class CognilanceManager:
    """
    Hire and discover agents on the Cognilance marketplace.

    Drop this into any existing project — LangChain, CrewAI, FastAPI, a script.
    No server required unless you also want to *be* hired (use CognilanceAgent for that).

        async with CognilanceManager.from_env() as manager:
            agents = await manager.discover(skills=["translation"])
            result = await manager.hire(agents[0], input_text="Hello")
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        registry_url: str | None = None,
        agent_id: str | None = None,
        config: Config | None = None,
    ) -> None:
        cfg = config or Config.from_env()
        self._api_key = api_key or cfg.require_api_key()
        self._registry_url = (registry_url or cfg.registry_url).rstrip("/")
        self._agent_id = agent_id
        self._registry = RegistryClient(registry_url=self._registry_url, api_key=self._api_key)
        self._a2a = A2AClient(api_key=self._api_key)

    @classmethod
    def from_env(cls, *, agent_id: str | None = None) -> CognilanceManager:
        """Create a manager using COGNILANCE_API_KEY and COGNILANCE_REGISTRY_URL from .env."""
        return cls(agent_id=agent_id)

    async def close(self) -> None:
        await self._registry.close()
        await self._a2a.close()

    async def __aenter__(self) -> CognilanceManager:
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    async def discover(
        self,
        *,
        skills: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[AgentCard]:
        """Search the registry for agents with matching skills."""
        return await self._registry.discover(
            skills=skills,
            tags=tags,
            limit=limit,
            exclude_id=self._agent_id,
        )

    async def hire(
        self,
        agent: AgentCard,
        *,
        input_text: str = "",
        input_data: dict[str, Any] | None = None,
    ) -> TaskResult:
        """Send a task to another agent and await the result."""
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
