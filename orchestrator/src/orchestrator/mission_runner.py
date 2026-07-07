"""Run orchestrator graph for a mission with event persistence."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from orchestrator.context import current_conversation_id, current_mission_id
from orchestrator.graph import ensure_graph
from orchestrator.missions.finalize import finalize_session_status
from orchestrator.missions.models import MissionStatus
from orchestrator.missions.store import MissionStore


def _ui_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": item["name"], "props": item.get("props") or {}}
        for item in (result.get("ui") or [])
        if item.get("type") == "ui" and item.get("name") != "text-card"
    ]


def _normalize_custom_event(chunk: dict[str, Any]) -> dict[str, Any] | None:
    if chunk.get("event"):
        return chunk
    if chunk.get("type") == "ui" and chunk.get("name") != "text-card":
        return {
            "event": "ui",
            "name": chunk.get("name"),
            "props": chunk.get("props") or {},
        }
    return None


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


async def stream_mission_graph(
    instruction: str,
    thread_id: str,
    *,
    history: list[BaseMessage] | None = None,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> AsyncIterator[str]:
    """Yield SSE lines while running the graph."""
    final: dict[str, Any] | None = None
    prior = list(history or [])
    if prior:
        input_messages = [*prior, HumanMessage(content=instruction)]
        config = _thread_config(str(uuid.uuid4()))
    else:
        input_messages = [HumanMessage(content=instruction)]
        config = _thread_config(thread_id)
    try:
        graph = await ensure_graph()
        async for mode, chunk in graph.astream(
            {"messages": input_messages},
            config=config,
            stream_mode=["custom", "values"],
        ):
            if mode == "custom" and isinstance(chunk, dict):
                event = _normalize_custom_event(chunk)
                if event:
                    if on_event:
                        await on_event(event)
                    yield f"data: {json.dumps(event)}\n\n"
            elif mode == "values":
                final = chunk
    except Exception as exc:
        error_event = {"event": "error", "message": str(exc)}
        if on_event:
            await on_event(error_event)
        yield f"data: {json.dumps(error_event)}\n\n"
        return

    if final and final.get("messages"):
        message = final["messages"][-1]
        payload = {
            "event": "final",
            "thread_id": thread_id,
            "text": message.content
            if isinstance(message.content, str)
            else str(message.content),
            "ui": _ui_items(final),
            "plan": final.get("plan") or {},
            "route": final.get("route"),
            "complexity": final.get("complexity"),
            "subtask_results": final.get("subtask_results") or [],
        }
        if on_event:
            await on_event(payload)
        yield f"data: {json.dumps(payload)}\n\n"

    done = {"event": "done", "thread_id": thread_id}
    if on_event:
        await on_event(done)
    yield f"data: {json.dumps(done)}\n\n"


async def run_mission(
    store: MissionStore,
    mission_id: str,
    *,
    history: list[BaseMessage] | None = None,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
) -> None:
    """Execute a mission to completion (used by background worker)."""
    mission = store.get_mission(mission_id)
    if not mission:
        return

    store.update_status(mission_id, MissionStatus.RUNNING)
    conv_token = current_conversation_id.set(mission.conversation_id or mission.thread_id)
    mission_token = current_mission_id.set(mission_id)
    final_text: str | None = None
    final_ui: list[dict[str, Any]] | None = None
    had_error = False
    error_message: str | None = None

    async def persist(event: dict[str, Any]) -> None:
        nonlocal final_text, final_ui, had_error, error_message
        store.append_event(mission_id, event)
        if event.get("event") == "error":
            had_error = True
            error_message = str(event.get("message") or "Mission failed")
        if event.get("event") == "final":
            final_text = event.get("text")
            final_ui = event.get("ui") or []
        if on_event:
            await on_event(event)

    try:
        async for _line in stream_mission_graph(
            mission.instruction,
            mission.thread_id,
            history=history,
            on_event=persist,
        ):
            pass
        finalize_session_status(
            store,
            mission,
            had_error=had_error,
            error_message=error_message,
            final_text=final_text,
            final_ui=final_ui,
        )
    except Exception as exc:
        store.update_status(mission_id, MissionStatus.FAILED, error=str(exc))
        await persist({"event": "error", "message": str(exc)})
    finally:
        current_conversation_id.reset(conv_token)
        current_mission_id.reset(mission_token)
