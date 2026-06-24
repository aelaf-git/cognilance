"""Planner — parallel complexity classification + registry catalog; builds dynamic plan."""

from __future__ import annotations

import asyncio
from typing import Literal

from cognilance import CognilanceManager
from cognilance.core.models import AgentCard
from pydantic import BaseModel, Field

from orchestrator.llm import get_llm, last_user_text
from orchestrator.registry_cache import find_agent_by_skill, get_catalog
from orchestrator.state import Plan, State, Subtask
from orchestrator.streaming import emit, emit_status, stream_llm

UI_COMPONENTS = """- research-sources: research summaries with linked sources
- data-chart: bar or line charts for numeric series
- code-findings: code review findings with severity badges"""

THINKING_SYSTEM = """You are the Cognilance planner — like Cursor's agent planner, but for any task.

Think out loud before acting. Write in clear prose (not JSON). Cover:
1. What the user is asking for and any constraints
2. What capabilities or tools are needed
3. Which marketplace agents could help (reference the catalog by name and skill)
4. Whether the task is simple (self-contained) or complex (needs specialists)
5. Your step-by-step plan for how execution should proceed

Be concise but thorough."""


class ComplexityDecision(BaseModel):
    complexity: Literal["simple", "complex"] = Field(
        description="simple = self-contained; complex = needs specialist agents"
    )
    reasoning: str = Field(description="Why this complexity level fits")


class PlanStep(BaseModel):
    title: str
    detail: str


class SubtaskPlan(BaseModel):
    id: str
    title: str
    instruction: str
    skill: str | None = Field(
        default=None,
        description="Registry skill slug when a specialist is needed",
    )
    depends_on: list[str] = Field(default_factory=list)


class PlannerDecision(BaseModel):
    reasoning: str
    steps: list[PlanStep]
    subtasks: list[SubtaskPlan] = Field(
        default_factory=list,
        description="Execution subtasks when complexity is complex",
    )
    suggested_ui: str | None = Field(
        default=None,
        description=f"Preferred rich UI component when hiring.\n{UI_COMPONENTS}",
    )


async def _classify_complexity(query: str, catalog_text: str) -> ComplexityDecision:
    llm = get_llm(temperature=0).with_structured_output(ComplexityDecision)
    return await llm.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "Classify whether the user's task is simple (answer directly) "
                    "or complex (requires specialist agents from the marketplace)."
                ),
            },
            {
                "role": "user",
                "content": f"User request:\n{query}\n\nMarketplace catalog:\n{catalog_text}",
            },
        ]
    )  # type: ignore[return-value]


def _resolve_subtasks(
    subtask_plans: list[SubtaskPlan],
    agents: list[AgentCard],
) -> list[Subtask]:
    resolved: list[Subtask] = []
    for item in subtask_plans:
        skill = (item.skill or "").strip() or None
        assignee = "thinking"
        if skill:
            match = find_agent_by_skill(agents, skill)
            assignee = match.name if match else "thinking"
        resolved.append(
            {
                "id": item.id,
                "title": item.title,
                "instruction": item.instruction,
                "skill": skill,
                "assignee": assignee,
                "depends_on": list(item.depends_on),
            }
        )
    return resolved


async def planner(state: State) -> dict:
    query = last_user_text(state.get("messages", []))
    emit_status("Planning…")

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        preview_catalog = state.get("catalog_text") or "Catalog not yet loaded."
        try:
            complexity_decision, (catalog_agents, catalog_text, cache_updates) = await asyncio.gather(
                _classify_complexity(query, preview_catalog),
                get_catalog(state, manager),
            )
        except Exception:
            complexity_decision = ComplexityDecision(
                complexity="simple",
                reasoning="Registry unavailable; answering directly.",
            )
            catalog_agents = []
            catalog_text = "No agents are registered in the marketplace."
            cache_updates = {}

        thinking = await stream_llm(
            get_llm(temperature=0.3),
            [
                {"role": "system", "content": THINKING_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{query}\n\n"
                        f"Complexity: {complexity_decision.complexity}\n\n"
                        f"Marketplace catalog:\n{catalog_text}"
                    ),
                },
            ],
            event="thinking",
        )
        emit("thinking_done", text=thinking)

        emit_status("Building execution plan…")
        llm = get_llm(temperature=0).with_structured_output(PlannerDecision)
        decision: PlannerDecision = await llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Build an execution plan using ONLY agents that exist in the catalog. "
                        "For complex tasks, define subtasks with ids and dependency edges. "
                        "Use exact skill slugs from the catalog. "
                        "If no agent matches a needed skill, omit the skill — it will fall back to thinking.\n\n"
                        f"Rich UI components:\n{UI_COMPONENTS}\n\n"
                        f"Marketplace catalog:\n{catalog_text}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{query}\n\n"
                        f"Complexity: {complexity_decision.complexity}\n"
                        f"Complexity reasoning: {complexity_decision.reasoning}\n\n"
                        f"Planner thinking:\n{thinking}"
                    ),
                },
            ]
        )  # type: ignore[assignment]

        complexity = complexity_decision.complexity
        route = "simple" if complexity == "simple" else "complex"
        subtasks = (
            _resolve_subtasks(decision.subtasks, catalog_agents)
            if route == "complex"
            else []
        )
        if route == "complex" and not subtasks:
            subtasks = [
                {
                    "id": "main",
                    "title": "Handle request",
                    "instruction": query,
                    "skill": None,
                    "assignee": "thinking",
                    "depends_on": [],
                }
            ]

        plan: Plan = {
            "reasoning": decision.reasoning,
            "suggested_ui": decision.suggested_ui,
            "thinking": thinking,
            "steps": [
                {"title": step.title, "detail": step.detail} for step in decision.steps
            ],
        }

        emit("plan", data={**plan, "complexity": complexity, "route": route, "subtasks": subtasks})
        emit("route_decision", route=route, complexity=complexity)

        return {
            **cache_updates,
            "complexity": complexity,
            "route": route,
            "thinking": thinking,
            "plan": plan,
            "subtasks": subtasks,
            "subtask_results": [],
            "final_text": "",
            "final_data": {},
            "answer_streamed": False,
        }
