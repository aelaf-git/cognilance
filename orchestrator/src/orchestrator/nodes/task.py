"""Task Agent — decompose plan, delegate subtasks in parallel layers, aggregate results."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any

from cognilance import CognilanceManager

from langchain_core.messages import BaseMessage

from orchestrator.integrations.client import IntegrationClient
from orchestrator.integrations.gmail_params import format_email_draft, format_send_email_result
from orchestrator.integrations.routing import (
    format_document_result,
    format_gmail_list_result,
    format_subscription_result,
    format_calendar_list_result,
    format_recurring_result,
)
from orchestrator.tools.web import format_web_fetch_result, format_web_search_result
from orchestrator.llm import get_llm, last_user_text, to_chat_messages
from orchestrator.state import State, Subtask, SubtaskResult
from orchestrator.streaming import emit, emit_status
from orchestrator.tools.router import ToolRouter


def _dependency_layers(subtasks: list[Subtask]) -> list[list[Subtask]]:
    """Topological sort into layers for parallel execution."""
    if not subtasks:
        return []

    by_id = {item["id"]: item for item in subtasks}
    indegree: dict[str, int] = {item["id"]: 0 for item in subtasks}
    dependents: dict[str, list[str]] = defaultdict(list)

    for item in subtasks:
        for dep in item.get("depends_on") or []:
            if dep not in by_id:
                continue
            indegree[item["id"]] += 1
            dependents[dep].append(item["id"])

    layers: list[list[Subtask]] = []
    ready = deque([sid for sid, degree in indegree.items() if degree == 0])

    while ready:
        layer_ids = list(ready)
        ready.clear()
        layer = [by_id[sid] for sid in layer_ids]
        layers.append(layer)
        for sid in layer_ids:
            for child in dependents[sid]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)

    remaining = [sid for sid, degree in indegree.items() if degree > 0]
    if remaining:
        seen = {item["id"] for layer in layers for item in layer}
        layers.append([by_id[sid] for sid in remaining if sid in by_id and sid not in seen])

    return layers


async def _run_subtask(
    subtask: Subtask,
    manager: CognilanceManager,
    router: ToolRouter,
    *,
    conversation: list[BaseMessage] | None = None,
    prior_results: dict[str, SubtaskResult] | None = None,
) -> SubtaskResult:
    subtask_id = subtask["id"]
    instruction = subtask.get("instruction") or ""
    if prior_results:
        for dep_id in subtask.get("depends_on") or []:
            prior = prior_results.get(dep_id)
            if prior and prior.get("text"):
                instruction = f"{instruction}\n\nContext from prior step:\n{prior['text']}"
    skill = subtask.get("skill")
    tool = subtask.get("tool")
    assignee = subtask.get("assignee") or "thinking"

    emit(
        "subtask_start",
        id=subtask_id,
        title=subtask.get("title", ""),
        assignee=assignee,
        skill=skill,
        tool=tool or (f"hire:{skill}" if skill else "thinking"),
        instruction=instruction,
    )
    emit_status(f"Running: {subtask.get('title', subtask_id)}")

    try:
        extra_input: dict[str, Any] = {
            "action": subtask.get("action"),
            "params": subtask.get("params"),
            "conversation": conversation,
            "plan_context": subtask.get("plan_context") or "",
            "subtask_id": subtask_id,
        }
        hire_skill = skill
        if not hire_skill and tool and str(tool).startswith("hire:"):
            hire_skill = str(tool).split(":", 1)[1]
        if hire_skill == "email-writing" and prior_results:
            for pr in prior_results.values():
                draft_data = pr.get("data") or {}
                if draft_data.get("status") == "draft" and draft_data.get("body"):
                    extra_input["prior_draft"] = draft_data
                    break
        result = await router.execute(
            manager,
            tool=tool,
            skill=skill,
            instruction=instruction,
            input_data=extra_input,
        )
        payload: SubtaskResult = {
            "subtask_id": subtask_id,
            "text": result.text,
            "data": result.data,
            "assignee": result.assignee,
            "status": result.status,
        }
        emit(
            "subtask_done",
            id=subtask_id,
            status=result.status,
            assignee=result.assignee,
            text=(result.text or "")[:500],
        )
        return payload
    except Exception as exc:
        payload = {
            "subtask_id": subtask_id,
            "text": str(exc),
            "data": {},
            "assignee": assignee,
            "status": "failed",
        }
        emit(
            "subtask_done",
            id=subtask_id,
            status="failed",
            assignee=assignee,
            text=str(exc)[:500],
        )
        return payload


def _merge_data(results: list[SubtaskResult]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for result in results:
        data = result.get("data") or {}
        for key, value in data.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key] = merged[key] + value
            elif key == "body":
                continue
            else:
                merged[key] = value
    return merged


def _result_facts(results: list[SubtaskResult]) -> str:
    parts: list[str] = []
    for result in results:
        if result.get("status") == "failed":
            parts.append(f"FAILED ({result.get('assignee', 'agent')}): {result.get('text', '')}")
            continue
        data = result.get("data") or {}
        if data.get("emails"):
            parts.append(format_gmail_list_result(data))
        elif data.get("events") is not None:
            parts.append(format_calendar_list_result(data))
        elif data.get("sources") and data.get("query"):
            parts.append(format_web_search_result(data))
        elif data.get("url") and data.get("content") is not None:
            parts.append(format_web_fetch_result(data))
        elif data.get("draft") or (data.get("status") == "draft" and data.get("body")):
            parts.append(format_email_draft(data))
        elif data.get("gmail_message_id") or data.get("status") == "sent" or (
            data.get("id") and data.get("sent_body")
        ):
            parts.append(format_send_email_result(data))
        elif data.get("document_id") or str(data.get("url", "")).startswith(
            "https://docs.google.com/document/"
        ):
            parts.append(format_document_result(data))
        elif data.get("subscription_id") or "stopped" in data:
            if data.get("kind") == "recurring_task" or data.get("instruction"):
                parts.append(format_recurring_result(data))
            else:
                parts.append(format_subscription_result(data))
        elif result.get("text"):
            parts.append(f"[{result.get('assignee', 'agent')}] {result.get('text')}")
    return "\n\n".join(parts).strip()


async def _synthesize_final(
    query: str,
    results: list[SubtaskResult],
    *,
    conversation: list[BaseMessage] | None = None,
) -> str:
    if not results:
        return ""

    if len(results) == 1 and results[0].get("status") == "failed":
        return results[0].get("text") or "The task failed."

    facts = _result_facts(results)
    if not facts:
        return results[0].get("text") or "" if len(results) == 1 else ""

    if len(results) == 1:
        data = results[0].get("data") or {}
        if data.get("draft") or (data.get("status") == "draft" and data.get("body")):
            return format_email_draft(data)
        if data.get("gmail_message_id") or data.get("status") == "sent" or (
            data.get("id") and data.get("sent_body")
        ):
            return format_send_email_result(data)
        if data.get("subscription_id") or "stopped" in data:
            if data.get("kind") == "recurring_task" or data.get("instruction"):
                return format_recurring_result(data)
            return format_subscription_result(data)
        if data.get("sources") and data.get("query"):
            return format_web_search_result(data)
        if data.get("url") and data.get("content") is not None and results[0].get("assignee") == "web":
            return format_web_fetch_result(data)

    llm = get_llm(temperature=0.3)
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are Cognilance replying in chat. "
                "Write a short, natural answer using the execution results below. "
                "Preserve links, counts, and facts exactly. "
                "Never mention tools, APIs, subscribe_inbox, or internal orchestration. "
                "Never claim an action succeeded if results say FAILED. "
                "Never claim an email was sent unless execution results include a Gmail message ID. "
                "For email drafts or sent emails, include the full subject and body exactly as shown. "
                "One to three sentences unless listing emails, documents, or showing an email draft."
            ),
        },
    ]
    if conversation:
        messages.extend(to_chat_messages(conversation))
    messages.append(
        {
            "role": "user",
            "content": f"User request:\n{query}\n\nExecution results:\n{facts}",
        }
    )
    try:
        response = await llm.ainvoke(messages)
        content = response.content
        return content if isinstance(content, str) else str(content)
    except Exception:
        return facts


async def task_agent(state: State) -> dict:
    from orchestrator.registry_cache import deserialize_agents

    subtasks = state.get("subtasks") or []
    query = last_user_text(state.get("messages", []))
    emit("execution_start")

    if not subtasks:
        emit("execution_done")
        return {"subtask_results": [], "final_text": "", "final_data": {}}

    catalog_agents = deserialize_agents(state.get("catalog_agents") or [])
    router = ToolRouter(catalog_agents=catalog_agents, integration_client=IntegrationClient())
    layers = _dependency_layers(subtasks)
    all_results: list[SubtaskResult] = []
    plan_context = str((state.get("thinking") or "")).strip()

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        results_by_id: dict[str, SubtaskResult] = {}
        for layer in layers:
            layer_results = await asyncio.gather(
                *[
                    _run_subtask(
                        {
                            **item,
                            "plan_context": item.get("plan_context") or plan_context,
                        },
                        manager,
                        router,
                        conversation=state.get("messages", []),
                        prior_results=results_by_id,
                    )
                    for item in layer
                ]
            )
            for item, result in zip(layer, layer_results):
                results_by_id[item["id"]] = result
            all_results.extend(layer_results)

    emit_status("Aggregating results…")
    final_text = await _synthesize_final(
        query,
        all_results,
        conversation=state.get("messages", []),
    )
    final_data = _merge_data(all_results)
    emit("execution_done")

    return {
        "subtask_results": all_results,
        "final_text": final_text,
        "final_data": final_data,
        "answer_streamed": False,
    }
