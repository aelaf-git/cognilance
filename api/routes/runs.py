"""Durable run inspection, resume, and cancel."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from api.deps import (
    board_store,
    cancel_mission_task,
    conv_store,
    mission_store,
    mission_task_active,
    organization_ids_for,
    register_mission_task,
    run_store,
    user_from,
)
from api.sse import sse_line, sse_response
from core.runtime.event_bus import event_bus
from core.runtime.missions.finalize import finalize_session_status
from core.runtime.missions.models import MissionStatus
from core.runtime.runner import stream_mission_graph
from core.runtime.board.models import BoardTaskStatus
from core.runtime.runs.models import Run, RunStatus, RunStep
from core.signals import record_feedback

router = APIRouter(prefix="/runs")

_RESUMABLE = {RunStatus.WAITING_APPROVAL, RunStatus.QUEUED}
_CANCELLABLE_MISSIONS = {
    MissionStatus.QUEUED,
    MissionStatus.RUNNING,
    MissionStatus.WAITING_APPROVAL,
}


def _require_run(run_id: str, request: Request) -> Run:
    """A member of the run's organization can see it. A run with no organization stays private."""
    user_id = user_from(request)
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.organization_id:
        if run.organization_id not in organization_ids_for(user_id):
            raise HTTPException(status_code=404, detail="Run not found")
    elif run.user_id and run.user_id != user_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _duration_ms(start, end) -> int:
    return max(0, int((end - start).total_seconds() * 1000))


def _trace(run: Run, steps: list[RunStep]) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """Add each step's elapsed time. Sums stay on the response and are not stored."""
    previous = run.created_at
    payloads: list[dict[str, Any]] = []
    specialists: dict[str, int] = {}
    tools: dict[str, int] = {}
    for step in steps:
        duration = _duration_ms(previous, step.created_at)
        payload = step.to_dict()
        payload["duration_ms"] = duration
        payloads.append(payload)
        if step.kind == "task_claimed":
            role = str(step.data.get("role") or "").strip()
            if role:
                specialists[role] = specialists.get(role, 0) + duration
        elif step.kind == "tool_call":
            tool = str(step.data.get("tool") or "").strip()
            if tool:
                tools[tool] = tools.get(tool, 0) + duration
        previous = step.created_at
    return payloads, {"specialists": specialists, "tools": tools}


@router.get("/{run_id}")
async def get_run(run_id: str, request: Request) -> JSONResponse:
    run = _require_run(run_id, request)
    steps, durations = _trace(run, run_store.list_steps(run_id))
    tasks = [
        task.to_dict()
        for task in board_store.list_for_run(
            run_id,
            organization_id=run.organization_id,
            user_id=None if run.organization_id else run.user_id,
        )
    ]
    return JSONResponse(
        content={
            "run": run.to_dict(),
            "steps": steps,
            "board_tasks": tasks,
            "durations": durations,
        }
    )


def _current_assistant_message(run: Run) -> str:
    conversation_id = str(run.conversation_id or "").strip()
    if conversation_id:
        messages = conv_store.list_messages(conversation_id)
        for message in reversed(messages):
            if message.role == "assistant" and str(message.content or "").strip():
                return str(message.content)
    return str(run.result_text or "")


def _producing_agent(run_id: str, message: str) -> str:
    done = [
        task
        for task in board_store.list_for_run(run_id)
        if task.status == BoardTaskStatus.DONE and str(task.result_text or "").strip()
    ]
    target = message.strip()
    for task in reversed(done):
        if task.result_text.strip() == target:
            return task.assignee_role
    if done:
        return done[-1].assignee_role
    return ""


@router.post("/{run_id}/feedback")
async def post_feedback(run_id: str, request: Request) -> JSONResponse:
    run = _require_run(run_id, request)
    raw = await request.body()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid feedback") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid feedback")
    rating = payload.get("rating")
    if isinstance(rating, bool) or not isinstance(rating, int) or rating not in (-1, 1):
        raise HTTPException(status_code=400, detail="Invalid feedback")
    note = str(payload.get("note") or "")
    revision = str(payload.get("revision") or "")
    message = _current_assistant_message(run)
    record_feedback(
        run.id,
        rating=rating,
        note=note,
        message=message,
        revision=revision,
        agent_id=_producing_agent(run.id, message),
    )
    return JSONResponse({"run_id": run.id, "recorded": True})


@router.post("/{run_id}/resume")
async def resume_run(run_id: str, request: Request) -> Any:
    run = _require_run(run_id, request)
    if run.status not in _RESUMABLE:
        raise HTTPException(status_code=409, detail="Run cannot be resumed")
    mission_id = run.mission_id or run.id
    if mission_task_active(mission_id):
        raise HTTPException(status_code=409, detail="Run is already running")
    raw = await request.body()
    payload: dict[str, Any] = json.loads(raw) if raw else {}
    approved = True if not isinstance(payload, dict) else bool(payload.get("approved", True))
    resume = {"approved": approved} if run.status == RunStatus.WAITING_APPROVAL else None
    if resume is not None:
        from api import deps

        deps.org_store.record_audit(
            user_from(request),
            run.organization_id or "",
            "approval.approved" if approved else "approval.rejected",
            run.id,
        )

    async def drive() -> None:
        final_text: str | None = None
        final_ui: list[dict[str, Any]] | None = None
        had_error = False
        error_message: str | None = None
        mission = mission_store.get_mission(mission_id)
        if mission and mission.status in _CANCELLABLE_MISSIONS:
            mission_store.update_status(mission_id, MissionStatus.RUNNING)

        async def persist(event: dict[str, Any]) -> None:
            nonlocal final_text, final_ui, had_error, error_message
            if event.get("event") == "error":
                had_error = True
                error_message = str(event.get("message") or "Run failed")
            if event.get("event") == "final":
                final_text = event.get("text")
                final_ui = event.get("ui") or []
            await event_bus.publish(mission_id, event)

        try:
            try:
                async for _line in stream_mission_graph(
                    run.instruction,
                    run.thread_id,
                    on_event=persist,
                    use_checkpointer=True,
                    run_id=run.id,
                    user_id=run.user_id,
                    organization_id=run.organization_id,
                    resume=resume,
                ):
                    current = mission_store.get_mission(mission_id)
                    if current and current.status == MissionStatus.CANCELLED:
                        break
            except asyncio.CancelledError:
                current = mission_store.get_mission(mission_id)
                if current and current.status in _CANCELLABLE_MISSIONS:
                    mission_store.update_status(
                        mission_id, MissionStatus.CANCELLED, error="Aborted by user"
                    )
                run_store.update_status(run.id, RunStatus.CANCELLED, error="Aborted by user")
                raise
            current = mission_store.get_mission(mission_id)
            stored = run_store.get_run(run.id)
            if stored and stored.status == RunStatus.WAITING_APPROVAL:
                return
            if current and current.status == MissionStatus.CANCELLED:
                return
            if current and current.status != MissionStatus.WAITING_APPROVAL:
                finalize_session_status(
                    mission_store,
                    current,
                    had_error=had_error,
                    error_message=error_message,
                    final_text=final_text,
                    final_ui=final_ui,
                )
        finally:
            await event_bus.close(mission_id)

    async def stream() -> AsyncIterator[str]:
        yield sse_line(
            {
                "event": "run_resumed",
                "run_id": run.id,
                "mission_id": mission_id,
                "thread_id": run.thread_id,
            }
        )
        queue = event_bus.attach(mission_id)
        task = asyncio.create_task(drive())
        register_mission_task(mission_id, task)
        try:
            async for event in event_bus.drain(queue):
                yield sse_line(event)
                current = mission_store.get_mission(mission_id)
                if current and current.status == MissionStatus.CANCELLED:
                    if not task.done():
                        task.cancel()
                    break
        finally:
            event_bus.detach(mission_id, queue)
            if not task.done():
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return sse_response(stream())


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request) -> JSONResponse:
    run = _require_run(run_id, request)
    mission_id = run.mission_id or run.id
    task_cancelled = cancel_mission_task(mission_id)
    run_store.update_status(run.id, RunStatus.CANCELLED, error="Aborted by user")
    mission = mission_store.get_mission(mission_id)
    if mission and mission.status in _CANCELLABLE_MISSIONS:
        mission_store.update_status(mission_id, MissionStatus.CANCELLED, error="Aborted by user")
        mission_store.append_event(mission_id, {"event": "session_aborted", "reason": "user"})
    return JSONResponse(
        content={
            "run_id": run.id,
            "status": "cancelled",
            "task_cancelled": task_cancelled,
        }
    )
