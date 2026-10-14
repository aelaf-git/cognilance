"""Local skill dispatch — resolve agent URL by skill and run a task (no marketplace hire)."""

from __future__ import annotations

from typing import Any

from cognilance import CognilanceManager
from cognilance.core.models import AgentCard

from orchestrator.context import current_user_id
from orchestrator.integrations.client import IntegrationClient
from orchestrator.registry_cache import find_agent_by_skill
from pipeline.streaming import emit
from tools.tool_proxy.grants import issue_grant, scopes_for_skill


class SkillRunner:
    """Dispatch work to a registered online agent by skill slug."""

    name = "run_skill"
    description = "Run a local agent by skill slug."

    def __init__(self, catalog_agents: list[AgentCard]) -> None:
        self._catalog = catalog_agents

    async def run(self, manager: CognilanceManager, input: dict[str, Any]):
        from tools.router import ToolResult

        skill = str(input.get("skill") or "").strip()
        instruction = str(input.get("instruction") or "")
        agent = find_agent_by_skill(self._catalog, skill) if skill else None
        tool_label = f"skill:{skill}" if skill else "skill"
        if not agent:
            from pipeline.nodes.thinking import run_thinking

            caps = IntegrationClient().capabilities_context(current_user_id.get())
            emit("tool_start", tool=tool_label, assignee="thinking")
            text, data = await run_thinking(
                instruction,
                stream=False,
                capabilities=caps,
                conversation=input.get("conversation"),
            )
            emit("tool_done", tool=tool_label, assignee="thinking", status="fallback")
            return ToolResult(
                text=text,
                data=data,
                assignee="thinking",
                status="fallback",
            )
        emit("tool_start", tool=tool_label, assignee=agent.name)
        skill_input: dict[str, Any] = {}
        proxy_scopes = scopes_for_skill(skill)
        if proxy_scopes:
            subtask_id = str(input.get("subtask_id") or manager._task_id)
            grant = issue_grant(
                user_id=current_user_id.get() or "",
                task_id=subtask_id,
                trace_id=manager.trace_id,
                scopes=proxy_scopes,
            )
            skill_input["orchestrator"] = grant.to_input_data()
        for key in ("prior_draft", "params", "action", "plan_context", "conversation_history"):
            if key in input and input[key] is not None:
                skill_input[key] = input[key]
        result = await manager.run_task(
            agent,
            input_text=instruction,
            input_data=skill_input or None,
        )
        emit(
            "tool_done",
            tool=tool_label,
            assignee=agent.name,
            status="completed",
        )
        return ToolResult(
            text=result.output.text or "",
            data=result.output.data or {},
            assignee=agent.name,
        )
