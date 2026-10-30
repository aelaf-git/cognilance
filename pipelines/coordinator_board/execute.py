"""Run one specialist brief. Judgment stays in the coordinator."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage

from agents.loader import get_role
from pipelines.coordinator_board.models import Brief


def format_brief(brief: Brief) -> str:
    lines = [
        f"Goal: {brief.goal.strip()}",
        f"Constraints: {'; '.join(brief.constraints) or 'none'}",
        f"Success criteria: {'; '.join(brief.success_criteria)}",
        f"Budget: {brief.budget or 'one pass'}",
    ]
    if brief.expected_output:
        lines.append("Expected output fields: " + json.dumps(brief.expected_output, default=str))
    if brief.context.strip():
        lines.append(f"Relevant context: {brief.context.strip()}")
    lines.append(
        "Return a structured result for this goal. "
        "Do not invent sources, links, or confirmation that a side effect happened."
    )
    return "\n".join(lines)


async def execute_brief(agent_id: str, brief: Brief) -> dict[str, Any]:
    """Hand a brief to the specialist executor and return ``{text, data, tool}``."""
    pack = get_role(agent_id)
    if pack is None:
        return {"text": "", "data": {"error": "no such agent"}, "tool": ""}
    instruction = format_brief(brief)
    messages = [HumanMessage(content=brief.context)] if brief.context.strip() else []
    from pipelines.coordinator_board import specialists as specialists_mod

    runner = getattr(specialists_mod, "_run_task_loop", None)
    if runner is None:
        import inspect

        from tools.registry import run_role_tool

        kwargs: dict[str, Any] = {"instruction": instruction}
        if "conversation" in inspect.signature(run_role_tool).parameters:
            kwargs["conversation"] = messages
        return await run_role_tool(pack, "thinking", **kwargs)
    return await runner(pack, instruction=instruction, messages=messages)
