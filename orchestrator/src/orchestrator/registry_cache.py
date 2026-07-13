"""Registry catalog cache stored in graph state per thread."""

from __future__ import annotations

import time
from typing import Any

from cognilance import CognilanceManager
from cognilance.core.models import AgentCard

from orchestrator.state import State

CATALOG_TTL_SECONDS = 60.0


def _serialize_agent(agent: AgentCard) -> dict[str, Any]:
    return agent.model_dump()


def _format_catalog(agents: list[AgentCard]) -> str:
    if not agents:
        return "No agents are registered in the marketplace."
    lines: list[str] = []
    for agent in agents:
        skills = ", ".join(skill.id or skill.name for skill in agent.skills)
        status = "online" if agent.online else "offline"
        lines.append(
            f"- {agent.name}: skills=[{skills}] ({status}) — {agent.description or 'no description'}"
        )
    return "\n".join(lines)


def deserialize_agents(raw: list[dict[str, Any]]) -> list[AgentCard]:
    return [AgentCard.model_validate(item) for item in raw]


def _deserialize_agents(raw: list[dict[str, Any]]) -> list[AgentCard]:
    return deserialize_agents(raw)


def _cache_valid(state: State) -> bool:
    fetched_at = state.get("catalog_fetched_at")
    agents = state.get("catalog_agents")
    if fetched_at is None or not agents:
        return False
    return (time.time() - fetched_at) < CATALOG_TTL_SECONDS


async def get_catalog(
    state: State,
    manager: CognilanceManager,
    *,
    force_refresh: bool = False,
) -> tuple[list[AgentCard], str, dict[str, Any]]:
    """Return catalog agents and text, refreshing from registry when cache is stale."""
    if not force_refresh and _cache_valid(state):
        agents = _deserialize_agents(state.get("catalog_agents") or [])
        catalog_text = state.get("catalog_text") or _format_catalog(agents)
        return agents, catalog_text, {}

    agents = await manager.discover(limit=50)
    catalog_text = _format_catalog(agents)
    updates = {
        "catalog_agents": [_serialize_agent(agent) for agent in agents],
        "catalog_text": catalog_text,
        "catalog_fetched_at": time.time(),
    }
    return agents, catalog_text, updates


def catalog_snapshot(agents: list[AgentCard]) -> list[dict[str, Any]]:
    """Compact agent list for session UI / stream events."""
    rows: list[dict[str, Any]] = []
    for agent in agents:
        skills = [skill.id or skill.name for skill in agent.skills]
        rows.append(
            {
                "name": agent.name,
                "online": bool(agent.online),
                "skills": skills,
                "url": getattr(agent, "url", None),
            }
        )
    return rows


def _normalize_skill(skill: str) -> str:
    return skill.strip().lower().replace("_", "-").replace(" ", "-")


_SKILL_ALIASES: dict[str, set[str]] = {
    "python-code": {"python-code", "python", "code-writing", "code-writer", "python-coding"},
    "research": {"research", "web-research"},
    "data-analysis": {"data-analysis", "data-analysis", "analytics", "charting"},
}


def _skill_matches(requested: str, candidate: str) -> bool:
    req = _normalize_skill(requested)
    cand = _normalize_skill(candidate)
    if req == cand:
        return True
    for aliases in _SKILL_ALIASES.values():
        if req in aliases and cand in aliases:
            return True
    return False


def find_agent_by_skill(agents: list[AgentCard], skill: str) -> AgentCard | None:
    """Pick the first online agent offering the given skill slug."""
    if not skill:
        return None
    for agent in agents:
        if not agent.online:
            continue
        for agent_skill in agent.skills:
            if _skill_matches(skill, agent_skill.name) or _skill_matches(skill, agent_skill.id):
                return agent
    return None


def has_agent_for_skill(agents: list[AgentCard], skill: str) -> bool:
    return find_agent_by_skill(agents, skill) is not None
