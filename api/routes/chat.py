"""Chat endpoints: streaming (durable run + SSE) and one-shot."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import HumanMessage

from api.deps import (
    conv_store,
    mission_store,
    register_mission_task,
    thread_config,
    user_from,
)
from api.sse import sse_line, sse_response
from core.context.conversations.title import (
    fallback_conversation_title,
    paraphrase_conversation_title,
)
from core.context.request import current_conversation_id, current_mission_id, current_user_id
from core.context.users.timezone import activate_user_timezone, client_timezone_from_request
from core.runtime.event_bus import event_bus
from core.runtime.missions.finalize import finalize_session_status
from core.runtime.missions.models import MissionStatus
from core.runtime.runner import stream_mission_graph
from core.runtime.runs.models import RunTrigger
from pipelines.coordinator_board.graph import ensure_graph

router = APIRouter()


def _ui_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": item["name"], "props": item.get("props") or {}}
        for item in (result.get("ui") or [])
        if item.get("type") == "ui" and item.get("name") != "text-card"
    ]


@router.post("/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    payload: dict[str, Any] = await request.json()
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    user_id = user_from(request)
    conversation_id = (
        str(payload.get("conversation_id") or payload.get("thread_id") or "").strip()
        or str(uuid.uuid4())
    )
    existing = conv_store.get_conversation(conversation_id, user_id=user_id)
    if existing is None and conv_store.get_conversation(conversation_id) is not None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    provisional_title = fallback_conversation_title(text)
    conv_store.ensure_conversation(conversation_id, title=provisional_title, user_id=user_id)
    regenerating = bool(payload.get("regenerate")) and existing is not None
    if regenerating:
        regenerating = conv_store.delete_last_assistant_message(conversation_id)
    prior_history = conv_store.to_langchain_messages(conversation_id)
    if (
        regenerating
        and prior_history
        and isinstance(prior_history[-1], HumanMessage)
        and str(prior_history[-1].content).strip() == text
    ):
        # The graph appends this prompt to history itself. Keep the persisted
        # user turn, but omit it here so regeneration does not duplicate it.
        prior_history = prior_history[:-1]
    else:
        conv_store.append_message(conversation_id, role="user", content=text)
    if len(prior_history) == 0:
        conversation_title = await paraphrase_conversation_title(text)
        conv_store.touch_conversation(conversation_id, title=conversation_title)
    else:
        current = conv_store.get_conversation(conversation_id)
        conversation_title = conv_store.display_title(current) if current else provisional_title
    thread_id = conversation_id
    mission = mission_store.create_mission(
        instruction=text, thread_id=thread_id, conversation_id=conversation_id, user_id=user_id
    )
    mission_id = mission.id
    current_user_id.set(user_id)
    client_tz = client_timezone_from_request(request, payload)
    if client_tz:
        activate_user_timezone(user_id, from_client=client_tz)

    async def run_and_mark() -> None:
        final_text: str | None = None
        final_ui: list[dict[str, Any]] | None = None
        had_error = False
        error_message: str | None = None
        mission_store.update_status(mission_id, MissionStatus.RUNNING)
        conv_token = current_conversation_id.set(conversation_id)
        mission_token = current_mission_id.set(mission_id)

        async def persist_with_status(event: dict[str, Any]) -> None:
            nonlocal final_text, final_ui, had_error, error_message
            if event.get("event") == "error":
                had_error = True
                error_message = str(event.get("message") or "Session failed")
            if event.get("event") == "final":
                final_text = event.get("text")
                final_ui = event.get("ui") or []
                if final_text:
                    rich_ui = [
                        item
                        for item in final_ui
                        if isinstance(item, dict) and item.get("name") != "text-card"
                    ]
                    conv_store.append_message(
                        conversation_id,
                        role="assistant",
                        content=str(final_text),
                        ui=json.dumps(rich_ui[-1]) if rich_ui else None,
                    )
            mission_store.append_event(mission_id, event)
            await event_bus.publish(mission_id, event)

        try:
            async for _line in stream_mission_graph(
                text,
                thread_id,
                history=prior_history,
                on_event=persist_with_status,
                use_checkpointer=True,
                run_id=mission_id,
                user_id=user_id,
                trigger=RunTrigger.MESSAGE,
            ):
                current = mission_store.get_mission(mission_id)
                if current and current.status == MissionStatus.CANCELLED:
                    break
            current = mission_store.get_mission(mission_id) or mission
            if current.status == MissionStatus.CANCELLED:
                return
            finalize_session_status(
                mission_store,
                current,
                had_error=had_error,
                error_message=error_message,
                final_text=final_text,
                final_ui=final_ui,
            )
        except asyncio.CancelledError:
            current = mission_store.get_mission(mission_id)
            if current and current.status not in {
                MissionStatus.CANCELLED,
                MissionStatus.FAILED,
                MissionStatus.COMPLETED,
            }:
                mission_store.update_status(
                    mission_id, MissionStatus.CANCELLED, error="Aborted by user"
                )
                abort_evt = {"event": "session_aborted", "reason": "user"}
                mission_store.append_event(mission_id, abort_evt)
                await event_bus.publish(mission_id, abort_evt)
            raise
        except Exception as exc:
            current = mission_store.get_mission(mission_id)
            if current and current.status != MissionStatus.CANCELLED:
                mission_store.update_status(mission_id, MissionStatus.FAILED, error=str(exc))
                err_evt = {"event": "error", "message": str(exc)}
                mission_store.append_event(mission_id, err_evt)
                await event_bus.publish(mission_id, err_evt)
        finally:
            await event_bus.close(mission_id)
            current_conversation_id.reset(conv_token)
            current_mission_id.reset(mission_token)

    async def stream() -> AsyncIterator[str]:
        yield sse_line(
            {
                "event": "session_created",
                "session_id": mission_id,
                "mission_id": mission_id,
                "thread_id": thread_id,
                "conversation_id": conversation_id,
                "session_type": mission.session_type.value,
                "title": conversation_title,
            }
        )
        # Attach before the producer starts so no events are lost.
        queue = event_bus.attach(mission_id)
        task = asyncio.create_task(run_and_mark())
        register_mission_task(mission_id, task)
        try:
            async for event in event_bus.drain(queue):
                yield sse_line(event)
                current = mission_store.get_mission(mission_id)
                if current and current.status == MissionStatus.CANCELLED:
                    if not task.done():
                        task.cancel()
                    break
            final = mission_store.get_mission(mission_id)
            if final and final.status == MissionStatus.CANCELLED:
                yield sse_line({"event": "session_aborted", "reason": "user"})
                yield sse_line({"event": "done", "thread_id": thread_id, "aborted": True})
        finally:
            event_bus.detach(mission_id, queue)
            if not task.done():
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return sse_response(
        stream(), extra_headers={"X-Session-Id": mission_id, "X-Mission-Id": mission_id}
    )


@router.post("/chat")
async def chat_message(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    thread_id = str(payload.get("thread_id") or "").strip() or str(uuid.uuid4())
    mission = mission_store.create_mission(instruction=text, thread_id=thread_id)
    mission_store.update_status(mission.id, MissionStatus.RUNNING)
    try:
        graph = await ensure_graph()
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=text)]}, config=thread_config(thread_id)
        )
        message = result["messages"][-1]
        response_text = (
            message.content if isinstance(message.content, str) else str(message.content)
        )
        ui = _ui_items(result)
        mission_store.update_status(
            mission.id, MissionStatus.COMPLETED, result_text=response_text, result_ui=ui
        )
        return JSONResponse(
            content={
                "mission_id": mission.id,
                "thread_id": thread_id,
                "text": response_text,
                "ui": ui,
                "plan": result.get("plan") or {},
                "route": result.get("route"),
                "complexity": result.get("complexity"),
                "subtask_results": result.get("subtask_results") or [],
            }
        )
    except Exception as exc:
        mission_store.update_status(mission.id, MissionStatus.FAILED, error=str(exc))
        return JSONResponse(
            status_code=500, content={"text": str(exc), "error": True, "mission_id": mission.id}
        )
