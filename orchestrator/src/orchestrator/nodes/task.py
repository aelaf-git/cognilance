"""Task Agent — decompose plan, delegate subtasks in parallel layers, aggregate results."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any

from cognilance import CognilanceManager

from orchestrator.llm import get_llm, last_user_text
from orchestrator.nodes.thinking import run_thinking
from orchestrator.registry_cache import find_agent_by_skill
from orchestrator.state import State, Subtask, SubtaskResult
from orchestrator.streaming import emit, emit_status


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
        # Cycle or missing deps — run everything left in one final layer
        seen = {item["id"] for layer in layers for item in layer}
        layers.append([by_id[sid] for sid in remaining if sid in by_id and sid not in seen])

    return layers


async def _run_subtask(
    subtask: Subtask,
    manager: CognilanceManager,
    catalog_agents: list,
) -> SubtaskResult:
    subtask_id = subtask["id"]
    instruction = subtask.get("instruction") or ""
    skill = subtask.get("skill")
    assignee = subtask.get("assignee") or "thinking"

    emit(
        "subtask_start",
        id=subtask_id,
        title=subtask.get("title", ""),
        assignee=assignee,
    )
    emit_status(f"Running: {subtask.get('title', subtask_id)}")

    try:
        if assignee != "thinking" and skill:
            agent = find_agent_by_skill(catalog_agents, skill)
            if agent:
                result = await manager.hire(agent, input_text=instruction)
                payload: SubtaskResult = {
                    "subtask_id": subtask_id,
                    "text": result.output.text or "",
                    "data": result.output.data or {},
                    "assignee": agent.name,
                    "status": "completed",
                }
                emit("subtask_done", id=subtask_id, status="completed", assignee=agent.name)
                return payload

        text, data = await run_thinking(instruction, stream=False)
        payload = {
            "subtask_id": subtask_id,
            "text": text,
            "data": data,
            "assignee": "thinking",
            "status": "completed",
        }
        emit("subtask_done", id=subtask_id, status="completed", assignee="thinking")
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


async def _synthesize_final(query: str, results: list[SubtaskResult]) -> str:
    if len(results) == 1:
        return results[0].get("text") or ""

    parts = [
        f"[{r.get('assignee', 'agent')}] {r.get('text', '')}"
        for r in results
        if r.get("text")
    ]
    combined = "\n\n".join(parts)
    llm = get_llm(temperature=0.3)
    response = await llm.ainvoke(
        [
            {
                "role": "system",
                "content": (
                    "Synthesize subtask results into one clear answer for the user. "
                    "Preserve key facts and structured details."
                ),
            },
            {
                "role": "user",
                "content": f"User request:\n{query}\n\nSubtask results:\n{combined}",
            },
        ]
    )
    content = response.content
    return content if isinstance(content, str) else str(content)


async def task_agent(state: State) -> dict:
    from orchestrator.registry_cache import deserialize_agents

    subtasks = state.get("subtasks") or []
    query = last_user_text(state.get("messages", []))
    emit("execution_start")

    if not subtasks:
        emit("execution_done")
        return {"subtask_results": [], "final_text": "", "final_data": {}}

    catalog_agents = deserialize_agents(state.get("catalog_agents") or [])
    layers = _dependency_layers(subtasks)
    all_results: list[SubtaskResult] = []

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        for layer in layers:
            layer_results = await asyncio.gather(
                *[_run_subtask(item, manager, catalog_agents) for item in layer]
            )
            all_results.extend(layer_results)

    emit_status("Aggregating results…")
    final_text = await _synthesize_final(query, all_results)
    final_data = _merge_data(all_results)
    emit("execution_done")

    return {
        "subtask_results": all_results,
        "final_text": final_text,
        "final_data": final_data,
        "answer_streamed": False,
    }
