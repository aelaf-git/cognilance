"""Sessions (user-facing) and missions (legacy aliases) backed by MissionStore."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.deps import (
    active_organization_id,
    cancel_mission_task,
    conv_store,
    mission_store,
    owner_filter,
    sub_store,
    user_from,
)
from api.sse import sse_line, sse_response
from core.context.subscriptions.session_sync import (
    enrich_session_dict,
    pause_listener_for_mission,
    start_listener_for_mission,
    stop_listener_for_mission,
)
from core.runtime.missions.models import MissionStatus
from core.runtime.missions.session_type import SessionType

router = APIRouter()

_TERMINAL = {MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED}


def _require_mission(mission_id: str, request: Request, label: str = "Session"):
    mission = mission_store.get_mission(mission_id, **owner_filter(user_from(request)))
    if not mission:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return mission


async def _instruction_from(request: Request) -> tuple[dict[str, Any], str, str | None]:
    payload: dict[str, Any] = await request.json()
    instruction = str(payload.get("instruction") or payload.get("text") or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction is required")
    thread_id = str(payload.get("thread_id") or "").strip() or None
    return payload, instruction, thread_id


# ---- sessions -----------------------------------------------------------------


@router.get("/sessions")
async def list_sessions(request: Request) -> JSONResponse:
    scope = owner_filter(user_from(request))
    conversation_id = str(request.query_params.get("conversation_id") or "").strip() or None
    if conversation_id:
        if not conv_store.get_conversation(conversation_id, **scope):
            raise HTTPException(status_code=404, detail="Conversation not found")
        missions = mission_store.list_missions_for_conversation(
            conversation_id, limit=50, **scope
        )
    else:
        missions = mission_store.list_missions(limit=50, **scope)
    return JSONResponse(
        content={"sessions": [enrich_session_dict(m, sub_store=sub_store) for m in missions]}
    )


@router.post("/sessions")
async def create_session(request: Request) -> JSONResponse:
    payload, instruction, thread_id = await _instruction_from(request)
    raw_type = str(payload.get("session_type") or "").strip() or None
    session_type = SessionType(raw_type) if raw_type in {"once", "recurring"} else None
    user_id = user_from(request)
    mission = mission_store.create_mission(
        instruction=instruction,
        thread_id=thread_id,
        session_type=session_type,
        user_id=user_id,
        organization_id=active_organization_id(user_id),
    )
    return JSONResponse(content=mission.to_session_dict())


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> JSONResponse:
    mission = _require_mission(session_id, request)
    return JSONResponse(content=enrich_session_dict(mission, sub_store=sub_store))


@router.post("/sessions/{session_id}/abort")
async def abort_session(session_id: str, request: Request) -> JSONResponse:
    _require_mission(session_id, request)
    cancelled_task = cancel_mission_task(session_id)
    stop_listener_for_mission(session_id, sub_store=sub_store, mission_store=mission_store)
    # Ensure one-shot runs are marked cancelled even without a listener.
    current = mission_store.get_mission(session_id, **owner_filter(user_from(request)))
    if current and current.status in {MissionStatus.RUNNING, MissionStatus.QUEUED}:
        mission_store.update_status(session_id, MissionStatus.CANCELLED, error="Aborted by user")
        mission_store.append_event(session_id, {"event": "session_aborted", "reason": "user"})
    return JSONResponse(
        content={"session_id": session_id, "status": "cancelled", "task_cancelled": cancelled_task}
    )


@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str, request: Request) -> JSONResponse:
    mission = _require_mission(session_id, request)
    if mission.session_type != SessionType.RECURRING:
        raise HTTPException(
            status_code=400, detail="Only long-running background sessions can be paused"
        )
    paused = pause_listener_for_mission(
        session_id, sub_store=sub_store, mission_store=mission_store
    )
    if not paused:
        raise HTTPException(
            status_code=400, detail="No active background subscription found for this session"
        )
    return JSONResponse(
        content=enrich_session_dict(
            mission_store.get_mission(session_id, **owner_filter(user_from(request))) or mission,
            sub_store=sub_store,
        )
    )


@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str, request: Request) -> JSONResponse:
    mission = _require_mission(session_id, request)
    if mission.session_type != SessionType.RECURRING:
        raise HTTPException(
            status_code=400, detail="Only long-running background sessions can be started"
        )
    started = start_listener_for_mission(
        session_id, sub_store=sub_store, mission_store=mission_store
    )
    if not started:
        raise HTTPException(
            status_code=400, detail="No background subscription found for this session"
        )
    return JSONResponse(
        content=enrich_session_dict(
            mission_store.get_mission(session_id, **owner_filter(user_from(request))) or mission,
            sub_store=sub_store,
        )
    )


@router.delete("/sessions/{session_id}")
@router.post("/sessions/{session_id}/dismiss")
async def dismiss_session(session_id: str, request: Request) -> JSONResponse:
    _require_mission(session_id, request)
    try:
        mission_store.hide_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(content={"session_id": session_id, "dismissed": True})


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str, request: Request) -> StreamingResponse:
    return await mission_events(session_id, request)


@router.get("/sessions/{session_id}/history")
async def session_history(session_id: str, request: Request) -> JSONResponse:
    mission = _require_mission(session_id, request)
    events = mission_store.list_events(session_id)
    for event in events:
        event.pop("_event_id", None)
    return JSONResponse(
        content={"events": events, "session": enrich_session_dict(mission, sub_store=sub_store)}
    )


# ---- missions (legacy) ----------------------------------------------------------


@router.get("/missions")
async def list_missions(request: Request) -> JSONResponse:
    missions = [
        m.to_session_dict()
        for m in mission_store.list_missions(limit=50, **owner_filter(user_from(request)))
    ]
    return JSONResponse(content={"missions": missions, "sessions": missions})


@router.post("/missions")
async def create_mission(request: Request) -> JSONResponse:
    _payload, instruction, thread_id = await _instruction_from(request)
    user_id = user_from(request)
    mission = mission_store.create_mission(
        instruction=instruction,
        thread_id=thread_id,
        user_id=user_id,
        organization_id=active_organization_id(user_id),
    )
    return JSONResponse(
        content={
            "mission_id": mission.id,
            "thread_id": mission.thread_id,
            "status": mission.status.value,
        }
    )


@router.get("/missions/{mission_id}")
async def get_mission(mission_id: str, request: Request) -> JSONResponse:
    return JSONResponse(content=_require_mission(mission_id, request, "Mission").to_dict())


@router.get("/missions/{mission_id}/events")
async def mission_events(mission_id: str, request: Request) -> StreamingResponse:
    _require_mission(mission_id, request, "Mission")
    after_id = int(request.query_params.get("after", "0") or "0")

    async def replay() -> AsyncIterator[str]:
        nonlocal after_id
        while True:
            events = mission_store.list_events(mission_id, after_id=after_id)
            for event in events:
                event_id = event.pop("_event_id", None)
                if event_id:
                    after_id = int(event_id)
                yield sse_line(event)
            current = mission_store.get_mission(mission_id)
            terminal = bool(
                current
                and current.status in _TERMINAL | {MissionStatus.WAITING_APPROVAL}
            )
            if current and current.session_type == SessionType.RECURRING:
                terminal = current.status == MissionStatus.CANCELLED
            if terminal:
                if not events:
                    yield sse_line({"event": "done", "thread_id": current.thread_id})
                break
            await asyncio.sleep(0.5)

    return sse_response(replay())
