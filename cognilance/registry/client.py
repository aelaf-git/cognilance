"""RegistryClient — talks to the Cognilance central server."""

from __future__ import annotations

from typing import Any

import httpx

from cognilance.core.models import AgentCard, AgentVisibility, Skill


class RegistryError(Exception):
    """Raised when a registry API call fails."""


class RegistryClient:
    def __init__(self, *, registry_url: str) -> None:
        self._registry_url = registry_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._registry_url,
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def register(
        self,
        *,
        name: str,
        url: str,
        skills: list[str],
        description: str = "",
        visibility: AgentVisibility = AgentVisibility.PUBLIC,
        tags: list[str] | None = None,
    ) -> AgentCard:
        payload = {
            "name": name,
            "url": url,
            "description": description,
            "skills": skills,
            "visibility": visibility.value,
            "tags": tags or [],
        }
        response = await self._client.post("/v1/agents", json=payload)
        if response.status_code >= 400:
            raise RegistryError(f"Failed to register agent: {response.text}")
        return self._parse_agent_card(response.json())

    async def heartbeat(self, agent_id: str) -> None:
        response = await self._client.post(f"/v1/agents/{agent_id}/heartbeat")
        if response.status_code >= 400:
            raise RegistryError(f"Heartbeat failed for {agent_id}: {response.text}")

    async def discover(
        self,
        *,
        skills: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
        exclude_id: str | None = None,
    ) -> list[AgentCard]:
        params: dict[str, Any] = {"limit": limit}
        if skills:
            params["skills"] = skills
        if tags:
            params["tags"] = tags
        if exclude_id:
            params["exclude"] = exclude_id

        response = await self._client.get("/v1/agents/discover", params=params)
        if response.status_code >= 400:
            raise RegistryError(f"Discovery failed: {response.text}")

        data = response.json()
        agents = data if isinstance(data, list) else data.get("agents", [])
        return [self._parse_agent_card(a) for a in agents]

    async def get_agent(self, agent_id: str) -> AgentCard:
        response = await self._client.get(f"/v1/agents/{agent_id}")
        if response.status_code == 404:
            raise RegistryError(f"Agent not found: {agent_id}")
        if response.status_code >= 400:
            raise RegistryError(f"Failed to get agent: {response.text}")
        return self._parse_agent_card(response.json())

    def _parse_agent_card(self, data: dict[str, Any]) -> AgentCard:
        skills = [
            Skill(
                id=s.get("id", s.get("name", "").lower().replace(" ", "-")),
                name=s.get("name", s.get("id", "")),
                description=s.get("description", ""),
                tags=s.get("tags", []),
            )
            for s in data.get("skills", [])
        ]
        if not skills and "skill_names" in data:
            skills = [Skill.from_name(n) for n in data["skill_names"]]

        visibility = AgentVisibility(data.get("visibility", AgentVisibility.PUBLIC))
        return AgentCard(
            id=data.get("id"),
            name=data["name"],
            description=data.get("description", ""),
            url=data["url"],
            version=data.get("version", "0.1.0"),
            skills=skills,
            visibility=visibility,
            tags=data.get("tags", []),
            online=data.get("online", True),
        )
