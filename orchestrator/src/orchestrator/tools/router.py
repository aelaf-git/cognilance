"""Orchestrator tools — marketplace hire and OAuth app integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from cognilance import CognilanceManager

from orchestrator.context import current_user_id
from orchestrator.integrations.client import IntegrationClient
from orchestrator.integrations.doc_params import prepare_google_doc_params
from orchestrator.integrations.registry import INTEGRATIONS
from orchestrator.integrations.routing import format_document_result
from orchestrator.registry_cache import find_agent_by_skill
from orchestrator.streaming import emit


@dataclass
class ToolResult:
    text: str
    data: dict[str, Any]
    assignee: str
    status: str = "completed"


class OrchestratorTool(Protocol):
    name: str
    description: str

    async def run(self, manager: CognilanceManager, input: dict[str, Any]) -> ToolResult: ...


class HireAgentTool:
    name = "hire_agent"
    description = "Hire a marketplace agent by skill slug."

    def __init__(self, catalog_agents: list) -> None:
        self._catalog = catalog_agents

    async def run(self, manager: CognilanceManager, input: dict[str, Any]) -> ToolResult:
        skill = str(input.get("skill") or "").strip()
        instruction = str(input.get("instruction") or "")
        agent = find_agent_by_skill(self._catalog, skill) if skill else None
        if not agent:
            from orchestrator.nodes.thinking import run_thinking

            caps = IntegrationClient().capabilities_context(current_user_id.get())
            emit("tool_start", tool=f"hire:{skill}", assignee="thinking")
            text, data = await run_thinking(
                instruction,
                stream=False,
                capabilities=caps,
            )
            emit("tool_done", tool=f"hire:{skill}", assignee="thinking", status="fallback")
            return ToolResult(
                text=text,
                data=data,
                assignee="thinking",
                status="fallback",
            )
        emit("tool_start", tool=f"hire:{skill}", assignee=agent.name)
        result = await manager.hire(agent, input_text=instruction)
        emit("tool_done", tool=f"hire:{skill}", assignee=agent.name, status="completed")
        return ToolResult(
            text=result.output.text or "",
            data=result.output.data or {},
            assignee=agent.name,
        )


class ToolRouter:
    def __init__(
        self,
        *,
        catalog_agents: list,
        integration_client: IntegrationClient | None = None,
    ) -> None:
        self._catalog = catalog_agents
        self._integrations = integration_client or IntegrationClient()
        self._hire = HireAgentTool(catalog_agents)

    async def execute(
        self,
        manager: CognilanceManager,
        *,
        tool: str | None,
        skill: str | None,
        instruction: str,
        input_data: dict[str, Any] | None = None,
    ) -> ToolResult:
        payload = {"instruction": instruction, **(input_data or {})}
        resolved = tool or (f"hire:{skill}" if skill else "thinking")

        if resolved.startswith("hire:"):
            hire_skill = resolved.split(":", 1)[1]
            if not find_agent_by_skill(self._catalog, hire_skill):
                from orchestrator.nodes.thinking import run_thinking

                caps = self._integrations.capabilities_context(current_user_id.get())
                emit("tool_start", tool=resolved, assignee="thinking")
                text, data = await run_thinking(instruction, stream=False, capabilities=caps)
                emit("tool_done", tool=resolved, assignee="thinking", status="fallback")
                return ToolResult(text=text, data=data, assignee="thinking", status="fallback")
            return await self._hire.run(manager, {**payload, "skill": hire_skill})

        if resolved.startswith("app:"):
            integration_id = resolved.split(":", 1)[1]
            if integration_id not in INTEGRATIONS:
                raise RuntimeError(f"Unknown integration: {integration_id}")
            user_id = current_user_id.get()
            if not self._integrations.is_connected(user_id, integration_id):
                raise RuntimeError(f"{integration_id} is not connected — connect it on the Integrations page")
            action = str(payload.get("action") or "").strip()
            if not action:
                raise RuntimeError(f"Integration action is required for app:{integration_id}")
            params = payload.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            if not params and instruction:
                params = {"query": instruction, "text": instruction, "body": instruction}
            if action in {"create_document", "write_document", "read_document"}:
                conversation = payload.get("conversation")
                params = await prepare_google_doc_params(
                    action,
                    instruction,
                    params,
                    conversation=conversation,
                )
            result = await self._integrations.run(user_id, integration_id, action, params)
            if action in {"create_document", "write_document", "read_document"}:
                summary = format_document_result(result)
            else:
                summary = self._integrations.summarize_result(integration_id, action, result)
            return ToolResult(
                text=summary,
                data=result,
                assignee=integration_id,
            )

        if resolved == "thinking":
            from orchestrator.nodes.thinking import run_thinking

            caps = self._integrations.capabilities_context(current_user_id.get())
            text, data = await run_thinking(instruction, stream=False, capabilities=caps)
            return ToolResult(text=text, data=data, assignee="thinking")

        if skill:
            if find_agent_by_skill(self._catalog, skill):
                return await self._hire.run(manager, {**payload, "skill": skill})
            from orchestrator.nodes.thinking import run_thinking

            caps = self._integrations.capabilities_context(current_user_id.get())
            text, data = await run_thinking(instruction, stream=False, capabilities=caps)
            return ToolResult(text=text, data=data, assignee="thinking", status="fallback")

        from orchestrator.nodes.thinking import run_thinking

        caps = self._integrations.capabilities_context(current_user_id.get())
        text, data = await run_thinking(instruction, stream=False, capabilities=caps)
        return ToolResult(text=text, data=data, assignee="thinking")
