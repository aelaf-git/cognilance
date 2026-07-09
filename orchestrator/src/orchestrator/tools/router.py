"""Orchestrator tools — marketplace hire and OAuth app integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from cognilance import CognilanceManager

from orchestrator.context import current_mission_id, current_user_id
from orchestrator.datetime_util import current_time_context, format_current_time_summary
from orchestrator.integrations.calendar_params import prepare_calendar_list_params
from orchestrator.integrations.client import IntegrationClient
from orchestrator.integrations.doc_params import prepare_google_doc_params
from orchestrator.subscriptions.recurring_params import prepare_recurring_subscribe_params
from orchestrator.integrations.registry import INTEGRATIONS
from orchestrator.integrations.gmail_params import format_email_draft, format_send_email_result
from orchestrator.integrations.routing import (
    format_document_result,
    format_recurring_result,
    format_subscription_result,
)
from orchestrator.tools.web import (
    format_web_fetch_result,
    format_web_search_result,
    web_fetch,
    web_search,
)
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
                conversation=input.get("conversation"),
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
                text, data = await run_thinking(
                    instruction,
                    stream=False,
                    capabilities=caps,
                    conversation=payload.get("conversation"),
                )
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
            if not params and instruction and action not in {"compose_email", "send_email"}:
                params = {"query": instruction, "text": instruction, "body": instruction}
            conversation = payload.get("conversation")
            if integration_id == "gmail" and action in {"compose_email", "send_email"}:
                from orchestrator.context import current_conversation_id
                from orchestrator.integrations.gmail_params import (
                    mark_email_draft_sent,
                    prepare_compose_email,
                    prepare_send_email_params,
                )

                conv_id = current_conversation_id.get() or ""
                if action == "compose_email":
                    params = await prepare_compose_email(
                        instruction,
                        params,
                        conversation=conversation,
                        conversation_id=conv_id,
                    )
                    summary = format_email_draft(params)
                    emit("tool_done", tool="app:gmail", assignee="gmail", status="completed")
                    return ToolResult(
                        text=summary,
                        data={**params, "draft": True},
                        assignee="gmail",
                    )
                params = await prepare_send_email_params(
                    instruction,
                    params,
                    conversation=conversation,
                    conversation_id=conv_id,
                )
            if action in {"create_document", "write_document", "read_document"}:
                params = await prepare_google_doc_params(
                    action,
                    instruction,
                    params,
                    conversation=conversation,
                    plan_context=str(payload.get("plan_context") or ""),
                )
            if action == "list_events" and integration_id == "google-calendar":
                params = prepare_calendar_list_params(instruction, params, user_id=user_id)
            if action in {"subscribe_inbox", "unsubscribe_inbox"}:
                from orchestrator.context import current_conversation_id

                if not params.get("conversation_id"):
                    conv = current_conversation_id.get()
                    if conv:
                        params["conversation_id"] = conv
            result = await self._integrations.run(user_id, integration_id, action, params)
            if action in {"create_document", "write_document", "read_document"}:
                summary = format_document_result(result)
            elif action == "send_email" and integration_id == "gmail":
                from orchestrator.context import current_conversation_id

                mark_email_draft_sent(current_conversation_id.get() or "")
                sent = {
                    **result,
                    "sent_body": params.get("body"),
                    "subject": params.get("subject"),
                    "to": params.get("to"),
                }
                summary = format_send_email_result(sent)
                result = sent
            elif action in {"subscribe_inbox", "unsubscribe_inbox"}:
                summary = format_subscription_result(result)
            else:
                summary = self._integrations.summarize_result(integration_id, action, result)
            return ToolResult(
                text=summary,
                data=result,
                assignee=integration_id,
            )

        if resolved == "web" or resolved.startswith("web:"):
            if resolved.startswith("web:"):
                action = resolved.split(":", 1)[1].strip()
            else:
                action = str(payload.get("action") or "search").strip()
            params = payload.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            if action == "fetch_url":
                url = str(params.get("url") or "").strip()
                if not url:
                    from orchestrator.tools.web import extract_urls

                    urls = extract_urls(instruction)
                    if urls:
                        url = urls[0]
                if not url:
                    raise RuntimeError("url is required for web:fetch_url")
                emit("tool_start", tool="web:fetch", assignee="web", action=action)
                result = await web_fetch(url)
                summary = format_web_fetch_result(result)
            elif action in {"search", "web_search"}:
                query = str(params.get("query") or instruction).strip()
                max_results = int(params.get("max_results", 6))
                emit("tool_start", tool="web:search", assignee="web", action=action)
                result = await web_search(query, max_results=max_results)
                summary = format_web_search_result(result)
            else:
                raise RuntimeError(f"Unknown web action: {action}")
            emit("tool_done", tool=f"web:{action}", assignee="web", status="completed")
            return ToolResult(text=summary, data=result, assignee="web")

        if resolved == "recurring" or resolved.startswith("recurring:"):
            if resolved.startswith("recurring:"):
                action = resolved.split(":", 1)[1].strip()
            else:
                action = str(payload.get("action") or "subscribe").strip()
            params = payload.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            from orchestrator.context import current_conversation_id
            from orchestrator.subscriptions.service import SubscriptionService

            conversation_id = str(
                params.get("conversation_id") or current_conversation_id.get() or ""
            ).strip()
            user_id = current_user_id.get()
            service = SubscriptionService(integration_client=self._integrations)
            emit("tool_start", tool=f"recurring:{action}", assignee="recurring", action=action)

            if action == "subscribe":
                if not conversation_id:
                    raise RuntimeError("conversation_id is required for recurring subscribe")
                params = prepare_recurring_subscribe_params(instruction, params)
                result = await service.subscribe_recurring_task(
                    user_id,
                    conversation_id=conversation_id,
                    instruction=str(params.get("instruction") or instruction),
                    poll_interval_seconds=int(params.get("poll_interval_seconds", 86_400)),
                    mission_id=current_mission_id.get() or None,
                )
            elif action == "unsubscribe":
                if not conversation_id:
                    raise RuntimeError("conversation_id is required for recurring unsubscribe")
                result = await service.unsubscribe_recurring_task(
                    user_id,
                    conversation_id=conversation_id,
                    subscription_id=str(params.get("subscription_id", "")).strip() or None,
                )
            else:
                raise RuntimeError(f"Unknown recurring action: {action}")

            emit("tool_done", tool=f"recurring:{action}", assignee="recurring", status="completed")
            summary = format_recurring_result(result)
            return ToolResult(text=summary, data=result, assignee="recurring")

        if resolved == "time" or resolved.startswith("time:"):
            user_id = current_user_id.get()
            action = (
                resolved.split(":", 1)[1].strip()
                if resolved.startswith("time:")
                else str(payload.get("action") or "now").strip()
            )
            if action != "now":
                raise RuntimeError(f"Unknown time action: {action}")
            emit("tool_start", tool="time:now", assignee="time", action=action)
            ctx = current_time_context(
                user_id=user_id,
                tz=str((payload.get("params") or {}).get("timezone", "")).strip() or None,
            )
            summary = format_current_time_summary(ctx, user_id=user_id)
            emit("tool_done", tool="time:now", assignee="time", status="completed")
            return ToolResult(text=summary, data=ctx, assignee="time")

        if resolved == "thinking":
            from orchestrator.nodes.thinking import run_thinking

            caps = self._integrations.capabilities_context(current_user_id.get())
            text, data = await run_thinking(
                instruction,
                stream=False,
                capabilities=caps,
                conversation=payload.get("conversation"),
            )
            return ToolResult(text=text, data=data, assignee="thinking")

        if skill:
            if find_agent_by_skill(self._catalog, skill):
                return await self._hire.run(manager, {**payload, "skill": skill})
            from orchestrator.nodes.thinking import run_thinking

            caps = self._integrations.capabilities_context(current_user_id.get())
            text, data = await run_thinking(
                instruction,
                stream=False,
                capabilities=caps,
                conversation=payload.get("conversation"),
            )
            return ToolResult(text=text, data=data, assignee="thinking", status="fallback")

        from orchestrator.nodes.thinking import run_thinking

        caps = self._integrations.capabilities_context(current_user_id.get())
        text, data = await run_thinking(
            instruction,
            stream=False,
            capabilities=caps,
            conversation=payload.get("conversation"),
        )
        return ToolResult(text=text, data=data, assignee="thinking")
