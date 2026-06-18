"""Agent registry business logic."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from prisma import Prisma
from prisma.models import Agent

from app.config import get_settings
from app.schemas import AgentResponse, RegisterAgentRequest


def _skill_objects(names: list[str]) -> list[dict[str, Any]]:
    return [
        {"id": name.lower().replace(" ", "-"), "name": name, "description": "", "tags": []}
        for name in names
    ]


def _as_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def agent_to_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        url=agent.url,
        description=agent.description,
        skills=_as_list(agent.skills),
        visibility=agent.visibility,
        tags=_as_list(agent.tags),
        online=agent.online,
        last_heartbeat=agent.lastHeartbeat,
        version=agent.version,
    )


async def register_agent(
    db: Prisma,
    *,
    body: RegisterAgentRequest,
) -> AgentResponse:
    now = datetime.now(timezone.utc)
    agent = await db.agent.create(
        data={
            "name": body.name,
            "url": body.url.rstrip("/"),
            "description": body.description,
            "skills": json.dumps(_skill_objects(body.skills)),
            "visibility": body.visibility,
            "tags": json.dumps(body.tags),
            "online": True,
            "lastHeartbeat": now,
        }
    )
    return agent_to_response(agent)


async def heartbeat(db: Prisma, *, agent_id: UUID | str) -> None:
    now = datetime.now(timezone.utc)
    result = await db.agent.update_many(
        where={"id": str(agent_id)},
        data={"online": True, "lastHeartbeat": now, "updatedAt": now},
    )
    if result == 0:
        raise LookupError("Agent not found")


async def get_agent(
    db: Prisma, *, agent_id: UUID | str
) -> AgentResponse:
    agent = await db.agent.find_first(where={"id": str(agent_id)})
    if agent is None:
        raise LookupError("Agent not found")
    return agent_to_response(agent)


async def discover_agents(
    db: Prisma,
    *,
    skills: list[str] | None = None,
    tags: list[str] | None = None,
    limit: int = 10,
    exclude_id: str | None = None,
) -> list[AgentResponse]:
    agents = await db.agent.find_many(where={"visibility": "public", "online": True})

    filtered: list[Agent] = []
    for agent in agents:
        if exclude_id and agent.id == exclude_id:
            continue
        agent_skills_list = _as_list(agent.skills)
        if skills:
            agent_skills = {s.get("id", "") for s in agent_skills_list} | {
                s.get("name", "") for s in agent_skills_list
            }
            if not all(skill in agent_skills for skill in skills):
                continue
        agent_tags = _as_list(agent.tags)
        if tags and not all(tag in agent_tags for tag in tags):
            continue
        filtered.append(agent)

    filtered.sort(key=lambda a: a.lastHeartbeat, reverse=True)
    return [agent_to_response(a) for a in filtered[:limit]]


async def mark_stale_agents_offline(db: Prisma) -> int:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.heartbeat_timeout_seconds)
    result = await db.agent.update_many(
        where={"online": True, "lastHeartbeat": {"lt": cutoff}},
        data={"online": False},
    )
    return result
