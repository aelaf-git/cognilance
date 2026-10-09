"""Deterministic router — single planning authority before any planner LLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cognilance.core.models import AgentCard
from langchain_core.messages import BaseMessage

from orchestrator.integrations.client import IntegrationClient
from orchestrator.registry_cache import find_agent_by_skill, has_agent_for_skill
from orchestrator.routing.integrations import integration_subtasks_for_query
from orchestrator.routing.recurring import recurring_subtasks_for_query
from orchestrator.routing.time import time_subtasks_for_query
from orchestrator.routing.web import web_subtasks_for_query
from orchestrator.state import Subtask


@dataclass(frozen=True)
class RouterPlan:
    """Deterministic execution plan (complex route)."""

    subtasks: list[Subtask]
    reasoning: str
    suggested_ui: str | None = None


def _wants_python_code(query: str) -> bool:
    q = query.lower()
    hints = (
        "python",
        "write code",
        "write a function",
        "write a script",
        "implement",
        "palindrome",
        "leetcode",
        "def ",
        "class ",
    )
    return any(hint in q for hint in hints)


def _python_subtasks(query: str, agents: list[AgentCard]) -> list[Subtask] | None:
    if not _wants_python_code(query):
        return None
    match = find_agent_by_skill(agents, "python-code")
    if match:
        return [
            {
                "id": "python-code",
                "title": "Write Python code",
                "instruction": query,
                "skill": "python-code",
                "tool": "hire:python-code",
                "assignee": match.name,
                "depends_on": [],
            }
        ]
    return [
        {
            "id": "python-code",
            "title": "Write Python code",
            "instruction": query,
            "skill": None,
            "tool": "thinking",
            "assignee": "thinking",
            "depends_on": [],
        }
    ]


def _apply_hire_fallback(
    subtasks: list[Subtask],
    agents: list[AgentCard],
) -> list[Subtask]:
    result: list[Subtask] = []
    for item in subtasks:
        st = dict(item)
        tool = (st.get("tool") or "").strip()
        skill = (st.get("skill") or "").strip() or None
        hire_skill: str | None = None
        if tool.startswith("hire:"):
            hire_skill = tool.split(":", 1)[1]
        elif skill:
            hire_skill = skill
        if hire_skill and not has_agent_for_skill(agents, hire_skill):
            original = st.get("instruction") or ""
            st["tool"] = "thinking"
            st["skill"] = None
            st["action"] = None
            st["params"] = None
            st["assignee"] = "thinking"
            st["instruction"] = (
                f"{original}\n\n"
                f"(No marketplace agent for '{hire_skill}' is available — "
                f"handle this request directly as the Cognilance orchestrator.)"
            )
        result.append(st)
    return result


class DeterministicRouter:
    """Route known intents without LLM. Returns None when LLM planning is needed."""

    def route(
        self,
        query: str,
        *,
        client: IntegrationClient,
        user_id: str,
        catalog_agents: list[AgentCard] | None = None,
        conversation: list[BaseMessage] | None = None,
    ) -> RouterPlan | None:
        agents = list(catalog_agents or [])

        forced = integration_subtasks_for_query(
            query,
            client,
            user_id,
            conversation=conversation,
            catalog_agents=agents,
        )
        if forced:
            return RouterPlan(
                subtasks=_apply_hire_fallback(forced, agents),
                reasoning="Deterministic integration / specialist hire route.",
            )

        forced_time = time_subtasks_for_query(query)
        if forced_time:
            return RouterPlan(
                subtasks=forced_time,
                reasoning="Deterministic current-time route.",
            )

        forced_recurring = recurring_subtasks_for_query(query)
        if forced_recurring:
            return RouterPlan(
                subtasks=forced_recurring,
                reasoning="Deterministic recurring-task route.",
            )

        forced_web = web_subtasks_for_query(query, catalog_agents=agents)
        if forced_web:
            return RouterPlan(
                subtasks=_apply_hire_fallback(forced_web, agents),
                reasoning="Deterministic web / scrape / link-validation route.",
            )

        forced_python = _python_subtasks(query, agents)
        if forced_python:
            return RouterPlan(
                subtasks=_apply_hire_fallback(forced_python, agents),
                reasoning="Deterministic python-code route.",
                suggested_ui="python-code",
            )

        return None


def router_plan_to_state(plan: RouterPlan) -> dict[str, Any]:
    """Build planner node return fields for a deterministic hit."""
    return {
        "complexity": "complex",
        "route": "complex",
        "thinking": plan.reasoning,
        "plan": {
            "reasoning": plan.reasoning,
            "suggested_ui": plan.suggested_ui,
            "thinking": plan.reasoning,
            "steps": [
                {
                    "title": st.get("title") or st.get("id") or "Task",
                    "detail": st.get("tool") or st.get("skill") or "execute",
                }
                for st in plan.subtasks
            ],
        },
        "subtasks": plan.subtasks,
        "subtask_results": [],
        "final_text": "",
        "final_data": {},
        "answer_streamed": False,
    }
