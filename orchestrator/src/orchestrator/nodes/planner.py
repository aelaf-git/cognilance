"""Planner — Cursor-style thinking and structured plan (no execution)."""

from __future__ import annotations

from typing import Literal

from cognilance import CognilanceManager
from cognilance.core.models import AgentCard
from pydantic import BaseModel, Field

from orchestrator.llm import get_llm, last_user_text
from orchestrator.state import Plan, State
from orchestrator.streaming import emit, emit_status, stream_llm

UI_COMPONENTS = """- research-sources: research summaries with linked sources
- data-chart: bar or line charts for numeric series
- code-findings: code review findings with severity badges"""

THINKING_SYSTEM = """You are the Cognilance planner — like Cursor's agent planner, but for any task.

Think out loud before acting. Write in clear prose (not JSON). Cover:
1. What the user is asking for and any constraints
2. What capabilities or tools are needed
3. Which marketplace agents could help (reference the catalog by name and skill)
4. Whether to hire a specialist or answer directly
5. Your step-by-step plan for how execution should proceed

Be concise but thorough. Use short paragraphs or numbered steps."""


class PlanStep(BaseModel):
    title: str = Field(description="Short step title shown during execution")
    detail: str = Field(description="What this step accomplishes")


class PlannerDecision(BaseModel):
    steps: list[PlanStep] = Field(
        description="Ordered steps the executor will run, like Cursor/Replit"
    )
    action: Literal["hire", "general"] = Field(
        description="hire a specialist from the registry, or answer directly"
    )
    skill: str | None = Field(
        default=None,
        description="Exact skill slug to discover when action is hire",
    )
    reasoning: str = Field(description="One-line summary of the plan")
    suggested_ui: str | None = Field(
        default=None,
        description=f"Preferred rich UI component when hiring.\n{UI_COMPONENTS}",
    )


def _format_catalog(agents: list[AgentCard]) -> str:
    if not agents:
        return "No agents are registered in the marketplace."
    lines: list[str] = []
    for agent in agents:
        skills = ", ".join(skill.name for skill in agent.skills)
        status = "online" if agent.online else "offline"
        lines.append(
            f"- {agent.name}: skills=[{skills}] ({status}) — {agent.description or 'no description'}"
        )
    return "\n".join(lines)


async def planner(state: State) -> dict:
    query = last_user_text(state.get("messages", []))
    emit_status("Scanning agent marketplace…")

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        catalog = await manager.discover(limit=50)
        catalog_text = _format_catalog(catalog)

        thinking = await stream_llm(
            get_llm(temperature=0.3),
            [
                {"role": "system", "content": THINKING_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{query}\n\n"
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
                        "Turn the planner's thinking into a concrete execution plan. "
                        "Steps will be shown to the user and executed in order — "
                        "like Cursor or Replit agents.\n\n"
                        "Pick hire only when a matching online agent skill exists.\n\n"
                        f"Rich UI components (hire only):\n{UI_COMPONENTS}\n\n"
                        f"Marketplace catalog:\n{catalog_text}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{query}\n\n"
                        f"Planner thinking:\n{thinking}"
                    ),
                },
            ]
        )  # type: ignore[assignment]

        plan: Plan = {
            "action": decision.action,
            "skill": decision.skill,
            "reasoning": decision.reasoning,
            "suggested_ui": decision.suggested_ui,
            "thinking": thinking,
            "catalog": catalog_text,
            "steps": [
                {"title": step.title, "detail": step.detail} for step in decision.steps
            ],
        }
        emit("plan", data=plan)
        return {"plan": plan}
