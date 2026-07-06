"""Planner — parallel complexity classification + registry catalog; builds dynamic plan."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from cognilance import CognilanceManager
from cognilance.core.models import AgentCard
from pydantic import BaseModel, Field

from orchestrator.context import current_user_id
from orchestrator.integrations.client import IntegrationClient
from orchestrator.integrations.routing import integration_subtasks_for_query
from orchestrator.llm import get_llm, last_user_text
from orchestrator.registry_cache import find_agent_by_skill, get_catalog, has_agent_for_skill
from orchestrator.state import Plan, State, Subtask
from orchestrator.streaming import emit, emit_status, stream_llm

UI_COMPONENTS = """- research-sources: research summaries with linked sources
- data-chart: bar or line charts for numeric series
- python-code: Python source code with filename and summary"""

THINKING_SYSTEM = """You are the Cognilance planner — like Cursor's agent planner, but for any task.

Think out loud before acting. Write in clear prose (not JSON). Cover:
1. What the user is asking for and any constraints
2. What capabilities or tools are needed — check which integrations are CONNECTED vs NOT CONNECTED
3. Which marketplace agents could help (reference the catalog by name and skill)
4. Whether the task is simple (self-contained) or complex (needs specialists or integrations)
5. Your step-by-step plan; if a required integration is not connected, say the user must connect it first
6. Never plan to use app:* tools that are NOT CONNECTED

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
    tool: str | None = Field(
        default=None,
        description="Tool slug: hire:<skill>, app:google-drive, app:gmail, app:google-calendar, app:notion, app:slack, app:github, or thinking",
    )
    action: str | None = Field(
        default=None,
        description="Integration action when tool is app:<integration>",
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Parameters for the integration action",
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


async def _classify_complexity(
    query: str,
    catalog_text: str,
    capabilities: str,
) -> ComplexityDecision:
    llm = get_llm(temperature=0).with_structured_output(ComplexityDecision)
    return await llm.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "Classify whether the user's task is simple (answer directly) "
                    "or complex (requires specialist agents or connected integrations). "
                    "Tasks that need research, data analysis, charts, generating Python code, "
                    "or calling external services (email, calendar, Slack, Google Docs, etc.) "
                    "are complex. "
                    "Creating or editing Google Docs is ALWAYS complex. "
                    "If the marketplace catalog is empty or no agent has the required skill, "
                    "the orchestrator handles the task itself via tool=thinking or connected integrations. "
                    "Classify as simple when the orchestrator can answer directly without specialists."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User request:\n{query}\n\n"
                    f"Tool access:\n{capabilities}\n\n"
                    f"Marketplace catalog:\n{catalog_text}"
                ),
            },
        ]
    )  # type: ignore[return-value]


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


def _force_python_subtask(query: str, agents: list[AgentCard]) -> list[Subtask] | None:
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


def _apply_orchestrator_fallback(
    subtasks: list[Subtask],
    agents: list[AgentCard],
) -> list[Subtask]:
    """When no marketplace agent exists for a hire, the orchestrator handles it."""
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


def _resolve_subtasks(
    subtask_plans: list[SubtaskPlan],
    agents: list[AgentCard],
    *,
    integration_client: IntegrationClient,
    user_id: str,
) -> list[Subtask]:
    resolved: list[Subtask] = []
    for item in subtask_plans:
        skill = (item.skill or "").strip() or None
        tool = (item.tool or "").strip() or None
        instruction = item.instruction
        action = item.action
        params = item.params
        assignee = "thinking"
        if tool and tool.startswith("app:"):
            app_id = tool.split(":", 1)[1]
            if not integration_client.is_connected(user_id, app_id):
                tool = "thinking"
                action = None
                params = None
                assignee = "thinking"
                instruction = (
                    f"{item.instruction}\n\n"
                    f"The plan required app:{app_id}, but it is NOT CONNECTED. "
                    f"Tell the user to connect {app_id} at /integrations, then retry."
                )
            else:
                assignee = app_id
        elif tool and tool.startswith("hire:"):
            hire_skill = tool.split(":", 1)[1]
            match = find_agent_by_skill(agents, hire_skill)
            if match:
                assignee = match.name
            else:
                tool = "thinking"
                skill = None
                assignee = "thinking"
                instruction = (
                    f"{item.instruction}\n\n"
                    f"(No marketplace agent for '{hire_skill}' — answer directly as orchestrator.)"
                )
        elif skill:
            match = find_agent_by_skill(agents, skill)
            if match:
                assignee = match.name
                if not tool:
                    tool = f"hire:{skill}"
            else:
                tool = "thinking"
                skill = None
                assignee = "thinking"
                instruction = (
                    f"{item.instruction}\n\n"
                    f"(No marketplace agent for '{item.skill}' — answer directly as orchestrator.)"
                )
        resolved.append(
            {
                "id": item.id,
                "title": item.title,
                "instruction": instruction,
                "skill": skill if tool != "thinking" else None,
                "tool": tool,
                "action": action,
                "params": params,
                "assignee": assignee,
                "depends_on": list(item.depends_on),
            }
        )
    return resolved


async def planner(state: State) -> dict:
    query = last_user_text(state.get("messages", []))
    emit_status("Planning…")
    user_id = current_user_id.get()
    app_service = IntegrationClient()
    capabilities = app_service.capabilities_context(user_id)

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        preview_catalog = state.get("catalog_text") or "Catalog not yet loaded."
        try:
            complexity_decision, (catalog_agents, catalog_text, cache_updates) = await asyncio.gather(
                _classify_complexity(query, preview_catalog, capabilities),
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
                        f"Tool access:\n{capabilities}\n\n"
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
                        "Build an execution plan using ONLY agents that exist in the catalog "
                        "and ONLY CONNECTED integrations from the tool access list. "
                        "For complex tasks, define subtasks with ids and dependency edges. "
                        "Set tool to hire:<skill>, app:<integration-id>, or thinking. "
                        "For app tools, set action to a supported action and params as needed. "
                        "For Google Docs (app:google-drive): use create_document with name + "
                        "content (actual document body, not the user's command); use write_document "
                        "with document_id, content, mode=append, and optional style "
                        "(bold, font_size, font_family). Reuse document_id from prior messages. "
                        "Use exact skill slugs from the catalog for hire tools. "
                        "If a needed integration is NOT CONNECTED, use thinking and tell the user to connect it. "
                        "If no agent matches a needed skill, use tool=thinking — the orchestrator "
                    "will handle the task itself. Never assign hire:<skill> unless that skill "
                    "appears in the marketplace catalog.\n\n"
                        f"{capabilities}\n\n"
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
            _resolve_subtasks(
                decision.subtasks,
                catalog_agents,
                integration_client=app_service,
                user_id=user_id,
            )
            if route == "complex"
            else []
        )

        forced_integration = integration_subtasks_for_query(
            query,
            app_service,
            user_id,
            conversation=state.get("messages", []),
        )
        if forced_integration:
            complexity = "complex"
            route = "complex"
            subtasks = forced_integration

        if route == "complex" and not subtasks:
            subtasks = [
                {
                    "id": "main",
                    "title": "Handle request",
                    "instruction": query,
                    "skill": None,
                    "tool": "thinking",
                    "assignee": "thinking",
                    "depends_on": [],
                }
            ]

        forced_python = _force_python_subtask(query, catalog_agents)
        if forced_python:
            complexity = "complex"
            route = "complex"
            subtasks = forced_python
            if not decision.suggested_ui:
                decision.suggested_ui = "python-code"

        if route == "complex" and subtasks:
            subtasks = _apply_orchestrator_fallback(subtasks, catalog_agents)

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
        emit("capabilities", text=capabilities)

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
