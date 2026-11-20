"""Run durable coordinator graph for a Run / mission with event bus + persistence."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage

from core.runtime.board.store import BoardStore
from core.context.request import current_conversation_id, current_mission_id
from core.runtime.missions.finalize import finalize_session_status
from core.runtime.missions.models import MissionStatus
from core.runtime.missions.store import MissionStore
from core.runtime.runs.models import RunStatus, RunTrigger
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.graph import ensure_graph
from core.runtime.event_bus import event_bus


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


def _interrupt_payload(snapshot: Any) -> dict[str, Any] | None:
    interrupts = getattr(snapshot, "interrupts", None) or ()
    if not interrupts:
        return None
    value = getattr(interrupts[0], "value", None)
    if isinstance(value, dict):
        return value
    return {"value": value}


def _is_interrupt_chunk(chunk: Any) -> bool:
    return isinstance(chunk, dict) and "__interrupt__" in chunk and "messages" not in chunk


async def _graph_input(
    graph: Any,
    config: dict[str, Any],
    *,
    fresh: dict[str, Any],
    resume: dict[str, Any] | None,
    use_checkpointer: bool,
) -> Any:
    """Continue a checkpoint, resume an approval, or start from the new messages."""
    if resume is not None:
        from langgraph.types import Command

        return Command(resume=resume)
    if not use_checkpointer:
        return fresh
    try:
        snapshot = await graph.aget_state(config)
    except Exception:
        return fresh
    if getattr(snapshot, "next", None) and not getattr(snapshot, "interrupts", None):
        return None
    return fresh


def recover_interrupted_runs() -> tuple[int, int]:
    """Requeue runs left running, and keep approval pauses where they are.

    Missions tied to a requeued run go back to queued. Missions still running
    with no run are marked failed by the existing stale recovery. A run in
    waiting_approval is not changed.
    """
    runs = RunStore()
    missions = MissionStore()
    runs.init_db()
    missions.init_db()
    requeued = runs.requeue_running()
    for run in requeued:
        mission_id = run.mission_id or run.id
        mission = missions.get_mission(mission_id)
        if mission and mission.status == MissionStatus.RUNNING:
            missions.update_status(mission_id, MissionStatus.QUEUED)
    for run in runs.list_by_status(RunStatus.WAITING_APPROVAL):
        mission_id = run.mission_id or run.id
        mission = missions.get_mission(mission_id)
        if mission and mission.status == MissionStatus.RUNNING:
            missions.update_status(mission_id, MissionStatus.WAITING_APPROVAL)
    failed = missions.recover_stale_running()
    return len(requeued), failed


async def stream_mission_graph(
    instruction: str,
    thread_id: str,
    *,
    history: list[BaseMessage] | None = None,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    use_checkpointer: bool = True,
    run_id: str | None = None,
    user_id: str | None = None,
    organization_id: str | None = None,
    client_message_id: str | None = None,
    trigger: RunTrigger = RunTrigger.MESSAGE,
    resume: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Yield SSE lines while running the durable coordinator graph."""
    final: dict[str, Any] | None = None
    prior = list(history or [])
    input_messages = [*prior, HumanMessage(content=instruction)]
    config = _thread_config(thread_id)

    runs = RunStore()
    runs.init_db()
    BoardStore().init_db()

    rid = run_id or current_mission_id.get() or thread_id
    if organization_id is None and user_id:
        from core.context.orgs.store import OrgStore

        organization_id = OrgStore().active_for_account(user_id)
    existing = runs.get_run(rid)
    if existing is None:
        runs.create_run(
            instruction=instruction,
            thread_id=thread_id,
            trigger=trigger,
            conversation_id=thread_id,
            user_id=user_id,
            organization_id=organization_id,
            client_message_id=client_message_id,
            mission_id=rid,
            run_id=rid,
        )
    runs.update_status(rid, RunStatus.RUNNING)
    runs.append_step(rid, kind="node_entered", text="graph_start", data={"trigger": trigger.value})

    paused: dict[str, Any] | None = None
    try:
        graph = await ensure_graph(with_checkpointer=use_checkpointer)
        graph_input = await _graph_input(
            graph,
            config,
            fresh={"messages": input_messages, "run_id": rid},
            resume=resume,
            use_checkpointer=use_checkpointer,
        )
        async for mode, chunk in graph.astream(
            graph_input,
            config=config,
            stream_mode=["custom", "values"],
        ):
            if mode == "custom" and isinstance(chunk, dict):
                event = _normalize_custom_event(chunk)
                if event:
                    if on_event:
                        await on_event(event)
                    yield f"data: {json.dumps(event)}\n\n"
            elif mode == "values" and not _is_interrupt_chunk(chunk):
                final = chunk
        if use_checkpointer:
            try:
                paused = _interrupt_payload(await graph.aget_state(config))
            except Exception:
                paused = None
    except Exception as exc:
        from langgraph.errors import GraphInterrupt

        if isinstance(exc, GraphInterrupt):
            paused = {}
            if exc.args and isinstance(exc.args[0], tuple) and exc.args[0]:
                value = getattr(exc.args[0][0], "value", None)
                paused = value if isinstance(value, dict) else {"value": value}
        else:
            runs.update_status(rid, RunStatus.FAILED, error=str(exc))
            error_event = {"event": "error", "message": str(exc)}
            if on_event:
                await on_event(error_event)
            yield f"data: {json.dumps(error_event)}\n\n"
            return

    if paused is not None:
        runs.update_status(
            rid,
            RunStatus.WAITING_APPROVAL,
            pending_approval=paused or None,
        )
        MissionStore().update_status(rid, MissionStatus.WAITING_APPROVAL)
    elif final and final.get("waiting_approval"):
        runs.update_status(
            rid,
            RunStatus.WAITING_APPROVAL,
            pending_approval=final.get("pending_approval"),
        )
        MissionStore().update_status(rid, MissionStatus.WAITING_APPROVAL)
    elif final:
        runs.update_status(
            rid,
            RunStatus.COMPLETED,
            result_text=(
                final["messages"][-1].content
                if final.get("messages")
                and isinstance(final["messages"][-1].content, str)
                else final.get("final_text")
            ),
            result_ui=_ui_items(final),
        )

    if paused is None and final and final.get("messages"):
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
            "run_id": rid,
            "text": message.content
            if isinstance(message.content, str)
            else str(message.content),
            "ui": _ui_items(final),
            "plan": final.get("plan") or {},
            "route": final.get("route"),
            "complexity": final.get("complexity"),
            "subtask_results": final.get("subtask_results") or [],
            "waiting_approval": bool(final.get("waiting_approval")),
            "pending_approval": final.get("pending_approval"),
            **doc_fields,
        }
        if on_event:
            await on_event(payload)
        yield f"data: {json.dumps(payload)}\n\n"

    done = {"event": "done", "thread_id": thread_id, "run_id": rid}
    if on_event:
        await on_event(done)
    yield f"data: {json.dumps(done)}\n\n"


async def run_mission(
    store: MissionStore,
    mission_id: str,
    *,
    history: list[BaseMessage] | None = None,
    on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    trigger: RunTrigger = RunTrigger.MESSAGE,
) -> None:
    """Execute a mission/run to completion (used by background worker)."""
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
            use_checkpointer=True,
            run_id=mission_id,
            user_id=mission.user_id,
            trigger=trigger,
        ):
            pass
        current = store.get_mission(mission_id) or mission
        if current.status != MissionStatus.WAITING_APPROVAL:
            finalize_session_status(
                store,
                current,
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
