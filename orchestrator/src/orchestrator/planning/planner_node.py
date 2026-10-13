"""Planner node — DeterministicRouter first; one LLM plan call only on miss."""

from __future__ import annotations

from typing import Any, Literal

from cognilance import CognilanceManager
from cognilance.core.models import AgentCard
from pydantic import BaseModel, Field

from orchestrator.context import current_user_id
from orchestrator.conversation.ack import acknowledgment_reply, is_acknowledgment
from orchestrator.drafts.store import DraftStore
from orchestrator.integrations.client import IntegrationClient
from orchestrator.llm import get_structured_llm, last_user_text, to_chat_messages
from orchestrator.registry_cache import (
    catalog_snapshot,
    find_agent_by_skill,
    get_catalog,
    has_agent_for_skill,
)
from orchestrator.routing.router import DeterministicRouter, router_plan_to_state
from orchestrator.state import Plan, State, Subtask
from orchestrator.streaming import emit, emit_status
from orchestrator.subscriptions.monitor_intent import is_monitor_request
from orchestrator.subscriptions.store import SubscriptionStore

UI_COMPONENTS = """- email-draft: composed email with to, subject, body, and send status
- research-sources: research summaries with linked sources
- data-chart: bar or line charts for numeric series
- python-code: Python source code with filename and summary"""

LLM_PLAN_SYSTEM = """You are the Cognilance planner for open-ended requests that the
deterministic router did not handle.

AGENT-FIRST: When a catalog agent has a matching skill, use hire:<skill>.
Use thinking, app:*, or web ONLY when no matching hireable skill exists.
Use ONLY CONNECTED integrations from the tool access list.
For complex tasks, define subtasks with ids and dependency edges.
Set tool to hire:<skill>, app:<integration-id>, web, time, recurring, or thinking.
Do NOT append validator (-validation) subtasks unless validation IS the user's request.
If a needed integration is NOT CONNECTED, use thinking and tell the user to connect it.
Classify complexity: simple = answer directly; complex = needs specialists or tools.
"""


class PlanStep(BaseModel):
    title: str
    detail: str


class SubtaskPlan(BaseModel):
    id: str
    title: str
    instruction: str
    skill: str | None = Field(default=None)
    tool: str | None = Field(default=None)
    action: str | None = Field(default=None)
    params: dict[str, Any] | None = Field(default=None)
    depends_on: list[str] = Field(default_factory=list)


class UnifiedPlannerDecision(BaseModel):
    complexity: Literal["simple", "complex"] = Field(
        description="simple = answer directly; complex = needs specialists or tools"
    )
    reasoning: str
    steps: list[PlanStep] = Field(default_factory=list)
    subtasks: list[SubtaskPlan] = Field(default_factory=list)
    suggested_ui: str | None = Field(default=None)


def _gmail_inbox_listener_active(conversation_id: str) -> bool:
    if not conversation_id:
        return False
    return any(
        s.integration == "gmail" and s.kind == "new_email"
        for s in SubscriptionStore().list_active_for_conversation(conversation_id)
    )


def _conversation_snippet(messages: list, *, limit: int = 10) -> str:
    if not messages:
        return ""
    recent = messages[-limit:]
    lines: list[str] = []
    for msg in to_chat_messages(recent):
        role = msg.get("role", "user")
        content = str(msg.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content[:800]}")
    return "\n\n".join(lines)


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
        elif tool == "web" or (tool and tool.startswith("web:")):
            if tool.startswith("web:"):
                action = action or tool.split(":", 1)[1]
                tool = "web"
            assignee = "web"
            action = action or "search"
        elif tool == "time" or (tool and tool.startswith("time:")):
            if tool.startswith("time:"):
                action = action or tool.split(":", 1)[1]
                tool = "time"
            assignee = "time"
            action = action or "now"
        elif tool == "recurring" or (tool and tool.startswith("recurring:")):
            if tool.startswith("recurring:"):
                action = action or tool.split(":", 1)[1]
                tool = "recurring"
            assignee = "recurring"
            action = action or "subscribe"
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


def _apply_orchestrator_fallback(
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


async def planner(state: State) -> dict:
    query = last_user_text(state.get("messages", []))
    emit_status("Planning…")
    user_id = current_user_id.get()
    app_service = IntegrationClient()
    capabilities = app_service.capabilities_context(user_id)

    from orchestrator.context import current_conversation_id

    conversation_id = current_conversation_id.get() or ""
    listener_active = _gmail_inbox_listener_active(conversation_id)

    if is_acknowledgment(query):
        if not (conversation_id and DraftStore().has_pending_email(conversation_id)):
            reply = acknowledgment_reply(listener_active=listener_active)
            plan: Plan = {
                "reasoning": "Brief acknowledgment — no further action needed.",
                "suggested_ui": None,
                "thinking": "",
                "steps": [],
            }
            emit("plan", data={**plan, "complexity": "simple", "route": "simple", "subtasks": []})
            emit("route_decision", route="simple", complexity="simple")
            emit("direct_reply", text=reply)
            return {
                "complexity": "simple",
                "route": "simple",
                "thinking": "",
                "plan": plan,
                "subtasks": [],
                "subtask_results": [],
                "final_text": reply,
                "final_data": {},
                "answer_streamed": False,
                "direct_reply": True,
            }

    if is_monitor_request(query) and listener_active:
        reply = (
            "I'm already watching your inbox in this chat. "
            "Say 'stop listening' if you want me to turn that off."
        )
        plan = {
            "reasoning": "Inbox listener already active for this conversation.",
            "suggested_ui": None,
            "thinking": "",
            "steps": [],
        }
        emit("plan", data={**plan, "complexity": "simple", "route": "simple", "subtasks": []})
        emit("route_decision", route="simple", complexity="simple")
        emit("direct_reply", text=reply)
        return {
            "complexity": "simple",
            "route": "simple",
            "thinking": "",
            "plan": plan,
            "subtasks": [],
            "subtask_results": [],
            "final_text": reply,
            "final_data": {},
            "answer_streamed": False,
            "direct_reply": True,
        }

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        emit_status("Discovering marketplace agents…")
        try:
            catalog_agents, catalog_text, cache_updates = await get_catalog(
                state, manager, force_refresh=True
            )
        except Exception:
            catalog_agents = []
            catalog_text = "No agents are registered in the marketplace."
            cache_updates = {}

        online = [a for a in catalog_agents if a.online]
        emit(
            "catalog",
            agents=catalog_snapshot(catalog_agents),
            online_count=len(online),
            total_count=len(catalog_agents),
            text=catalog_text,
        )

        # --- Router first: no planner LLM on hit ---
        router_hit = DeterministicRouter().route(
            query,
            client=app_service,
            user_id=user_id,
            catalog_agents=catalog_agents,
            conversation=state.get("messages", []),
        )
        if router_hit:
            state_fields = router_plan_to_state(router_hit)
            thinking = router_hit.reasoning
            emit("thinking", text=thinking)
            emit("thinking_done", text=thinking)
            emit(
                "plan",
                data={
                    **state_fields["plan"],
                    "complexity": "complex",
                    "route": "complex",
                    "subtasks": state_fields["subtasks"],
                },
            )
            emit("route_decision", route="complex", complexity="complex")
            emit("capabilities", text=capabilities)
            return {**cache_updates, **state_fields}

        # --- Miss: one unified LLM plan call ---
        emit_status("Building execution plan…")
        llm = get_structured_llm(UnifiedPlannerDecision, temperature=0)
        try:
            decision: UnifiedPlannerDecision = await llm.ainvoke(
                [
                    {
                        "role": "system",
                        "content": (
                            f"{LLM_PLAN_SYSTEM}\n\n"
                            f"{capabilities}\n\n"
                            f"Rich UI components:\n{UI_COMPONENTS}\n\n"
                            f"Marketplace catalog:\n{catalog_text}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"User request:\n{query}\n\n"
                            f"Recent conversation:\n{_conversation_snippet(state.get('messages', []))}"
                        ),
                    },
                ]
            )  # type: ignore[assignment]
        except Exception:
            decision = UnifiedPlannerDecision(
                complexity="simple",
                reasoning="Plan construction failed; answering directly.",
                steps=[],
                subtasks=[],
            )

        thinking = decision.reasoning
        emit("thinking", text=thinking)
        emit("thinking_done", text=thinking)

        complexity = decision.complexity
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

        if route == "complex" and subtasks:
            subtasks = _apply_orchestrator_fallback(subtasks, catalog_agents)

        plan = {
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
