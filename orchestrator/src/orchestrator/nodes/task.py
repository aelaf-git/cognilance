"""Task Agent — decompose plan, delegate subtasks in parallel layers, aggregate results."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any

from cognilance import CognilanceManager

from langchain_core.messages import BaseMessage

from orchestrator.integrations.client import IntegrationClient
from orchestrator.integrations.routing import format_document_result, format_gmail_list_result
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
) -> SubtaskResult:
    subtask_id = subtask["id"]
    instruction = subtask.get("instruction") or ""
    skill = subtask.get("skill")
    tool = subtask.get("tool")
    assignee = subtask.get("assignee") or "thinking"

    emit(
        "subtask_start",
        id=subtask_id,
        title=subtask.get("title", ""),
        assignee=assignee,
        tool=tool or (f"hire:{skill}" if skill else "thinking"),
    )
    emit_status(f"Running: {subtask.get('title', subtask_id)}")

    try:
        result = await router.execute(
            manager,
            tool=tool,
            skill=skill,
            instruction=instruction,
            input_data={
                "action": subtask.get("action"),
                "params": subtask.get("params"),
                "conversation": conversation,
            },
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
        emit("subtask_done", id=subtask_id, status="failed", assignee=assignee)
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
        elif data.get("document_id") or str(data.get("url", "")).startswith(
            "https://docs.google.com/document/"
        ):
            parts.append(format_document_result(data))
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

    llm = get_llm(temperature=0.3)
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are Cognilance — an AI-native orchestrator. "
                "Answer the user naturally using the execution results below. "
                "Preserve links, counts, and facts exactly. "
                "Never claim an action succeeded if the results say FAILED. "
                "Never invent API outcomes that are not in the results."
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

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        for layer in layers:
            layer_results = await asyncio.gather(
                *[
                    _run_subtask(
                        item,
                        manager,
                        router,
                        conversation=state.get("messages", []),
                    )
                    for item in layer
                ]
            )
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
