"""Trace collection and query logic."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from prisma import Prisma
from prisma.models import TraceEvent

from app.schemas import TraceEventIn, TraceSummary


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _event_to_dict(event: TraceEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "trace_id": event.traceId,
        "task_id": event.taskId,
        "parent_task_id": event.parentTaskId,
        "depth": event.depth,
        "agent_name": event.agentName,
        "type": event.eventType,
        "text": event.text,
        "data": _as_dict(event.data),
        "timestamp": event.timestamp.isoformat(),
    }


async def ingest_event(
    db: Prisma,
    *,
    body: TraceEventIn,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    ts = body.timestamp or now
    event_id = body.id if body.id else str(uuid.uuid4())

    event_data: dict[str, Any] = {
        "id": event_id,
        "traceId": body.trace_id,
        "taskId": body.task_id,
        "parentTaskId": body.parent_task_id,
        "depth": body.depth,
        "agentName": body.agent_name,
        "eventType": body.type,
        "text": body.text,
        "data": json.dumps(body.data),
        "timestamp": ts,
    }
    event = await db.traceevent.create(data=event_data)

    index = await db.traceindex.find_unique(where={"traceId": body.trace_id})
    if index is None:
        index_data: dict[str, Any] = {
            "traceId": body.trace_id,
            "firstEventAt": ts,
            "lastEventAt": ts,
            "eventCount": 1,
        }
        await db.traceindex.create(data=index_data)
    else:
        await db.traceindex.update(
            where={"traceId": body.trace_id},
            data={
                "lastEventAt": ts,
                "eventCount": {"increment": 1},
                "updatedAt": now,
            },
        )

    return _event_to_dict(event)


def _summarize(events: list[TraceEvent], trace_id: str) -> TraceSummary:
    root = next(
        (e for e in events if e.eventType in ("task_received", "hire_started")),
        events[0],
    )
    failed = any(e.eventType in ("task_failed", "hire_failed") for e in events)
    completed = any(e.eventType == "task_completed" and e.depth == 0 for e in events) or any(
        e.eventType == "hire_completed" and e.depth == 0 for e in events
    )
    return TraceSummary(
        trace_id=trace_id,
        started_at=events[0].timestamp,
        last_at=events[-1].timestamp,
        root_text=root.text,
        root_agent=root.agentName,
        event_count=len(events),
        agents=sorted({e.agentName for e in events if e.agentName}),
        status="failed" if failed else ("completed" if completed else "working"),
    )


async def list_traces(db: Prisma, *, limit: int = 50) -> list[TraceSummary]:
    indices = await db.traceindex.find_many(
        order={"lastEventAt": "desc"},
        take=limit,
    )
    summaries: list[TraceSummary] = []
    for index in indices:
        events = await db.traceevent.find_many(
            where={"traceId": index.traceId},
            order={"timestamp": "asc"},
        )
        if events:
            summaries.append(_summarize(events, index.traceId))
    return summaries


async def get_trace(db: Prisma, *, trace_id: str) -> list[dict[str, Any]]:
    events = await db.traceevent.find_many(
        where={"traceId": trace_id},
        order={"timestamp": "asc"},
    )
    if not events:
        raise LookupError("Trace not found")
    return [_event_to_dict(e) for e in events]
