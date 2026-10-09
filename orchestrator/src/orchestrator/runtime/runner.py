"""Run orchestrator graph for a mission with event bus + persistence."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage

from orchestrator.context import current_conversation_id, current_mission_id
from orchestrator.graph import ensure_graph
from orchestrator.missions.finalize import finalize_session_status
from orchestrator.missions.models import MissionStatus
from orchestrator.missions.store import MissionStore
from orchestrator.runtime.event_bus import event_bus


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
    use_checkpointer: bool = False,
) -> AsyncIterator[str]:
    """Yield SSE lines while running the graph.

    ConversationStore is the chat memory source of truth. By default chat runs
    do not resume LangGraph checkpoints across turns (use_checkpointer=False):
    history is passed as messages; thread_id stays = conversation_id.
    """
    final: dict[str, Any] | None = None
    prior = list(history or [])
    # Always conversation_id as thread_id — never random orphan checkpoints.
    input_messages = [*prior, HumanMessage(content=instruction)]
    config = _thread_config(thread_id)
    try:
        graph = await ensure_graph(with_checkpointer=use_checkpointer)
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
        final_data = final.get("final_data") or {}
        doc_fields: dict[str, str] = {}
        document_id = str(final_data.get("document_id") or "").strip()
        if document_id:
            url = str(final_data.get("url") or "").strip()
            if not url:
                url = f"https://docs.google.com/document/d/{document_id}/edit"
            doc_fields = {
                "document_id": document_id,
                "document_url": url,
                "document_title": str(
                    final_data.get("title") or final_data.get("name") or "Google Doc"
                ),
            }
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
            **doc_fields,
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
        await event_bus.publish(mission_id, event)
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
            use_checkpointer=False,
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
        await event_bus.close(mission_id)
        current_conversation_id.reset(conv_token)
        current_mission_id.reset(mission_token)
