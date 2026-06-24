"""Planner agent — discovers registry agents, plans hires, and executes them."""

from __future__ import annotations

import uuid
from typing import Literal

from cognilance import CognilanceManager
from cognilance.core.models import AgentCard
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from orchestrator.llm import get_llm, last_user_text
from orchestrator.state import HireResult, Plan, State

UI_COMPONENTS = """- research-sources: research summaries with linked sources
- data-chart: bar or line charts for numeric series
- code-findings: code review findings with severity badges
- text-card: plain formatted answer when no rich visualization fits"""


class PlannerDecision(BaseModel):
    action: Literal["hire", "general"] = Field(
        description="hire a specialist from the registry, or answer directly"
    )
    skill: str | None = Field(
        default=None,
        description="Exact skill slug to discover when action is hire (e.g. research, data-analysis, code-review)",
    )
    reasoning: str = Field(description="Short explanation of the plan")
    suggested_ui: str | None = Field(
        default=None,
        description=f"Preferred UI component for the UI agent.\n{UI_COMPONENTS}",
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

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        catalog = await manager.discover(limit=50)
        llm = get_llm(temperature=0).with_structured_output(PlannerDecision)
        decision: PlannerDecision = await llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You are the Cognilance planner. Study the user's request and the "
                        "marketplace catalog, then decide whether to hire a specialist agent "
                        "or answer directly.\n\n"
                        "When hiring, set skill to an exact slug from the catalog. "
                        "Prefer online agents. Pick a suggested_ui component when hiring.\n\n"
                        f"Available UI components:\n{UI_COMPONENTS}\n\n"
                        f"Marketplace catalog:\n{_format_catalog(catalog)}"
                    ),
                },
                {"role": "user", "content": query},
            ]
        )  # type: ignore[assignment]

        plan: Plan = {
            "action": decision.action,
            "skill": decision.skill,
            "reasoning": decision.reasoning,
            "suggested_ui": decision.suggested_ui,
        }

        if decision.action == "general":
            response = await get_llm(temperature=0.4).ainvoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are the Cognilance orchestrator. Answer the user directly "
                            "and concisely. Mention which marketplace specialist could help "
                            "if relevant."
                        ),
                    },
                    {"role": "user", "content": query},
                ]
            )
            text = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            )
            hire_result: HireResult = {
                "mode": "general",
                "text": text,
                "data": {"body": text},
                "skill": None,
                "agent_name": None,
            }
            return {"plan": plan, "hire_result": hire_result}

        skill = (decision.skill or "").strip()
        if not skill:
            hire_result = {
                "mode": "error",
                "text": "Planner chose hire but did not specify a skill.",
                "data": {},
                "skill": None,
                "agent_name": None,
            }
            return {"plan": plan, "hire_result": hire_result}

        agents = await manager.discover(skills=[skill], limit=5)
        if not agents:
            hire_result = {
                "mode": "error",
                "text": (
                    f"No agent offering the '{skill}' skill is online right now. "
                    "Start the matching agent in /agents and try again."
                ),
                "data": {},
                "skill": skill,
                "agent_name": None,
            }
            return {"plan": plan, "hire_result": hire_result}

        chosen = agents[0]
        result = await manager.hire(chosen, input_text=query)
        hire_result = {
            "mode": "hired",
            "text": result.output.text or "",
            "data": result.output.data or {},
            "skill": skill,
            "agent_name": chosen.name,
        }
        return {"plan": plan, "hire_result": hire_result}
