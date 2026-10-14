"""Trace collection and query logic."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TraceEvent, TraceIndex
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
        "trace_id": event.trace_id,
        "task_id": event.task_id,
        "parent_task_id": event.parent_task_id,
        "depth": event.depth,
        "agent_name": event.agent_name,
        "type": event.event_type,
        "text": event.text,
        "data": _as_dict(event.data),
        "timestamp": event.timestamp.isoformat(),
    }


async def ingest_event(
    db: AsyncSession,
    *,
    body: TraceEventIn,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    ts = body.timestamp or now
    event_id = body.id if body.id else str(uuid.uuid4())

    event = TraceEvent(
        id=event_id,
        trace_id=body.trace_id,
        task_id=body.task_id,
        parent_task_id=body.parent_task_id,
        depth=body.depth,
        agent_name=body.agent_name,
        event_type=body.type,
        text=body.text,
        data=json.dumps(body.data),
        timestamp=ts,
    )
    db.add(event)

    index = await db.get(TraceIndex, body.trace_id)
    if index is None:
        db.add(
            TraceIndex(
                trace_id=body.trace_id,
                first_event_at=ts,
                last_event_at=ts,
                event_count=1,
                updated_at=now,
            )
        )
    else:
        index.last_event_at = ts
        index.event_count = int(index.event_count or 0) + 1
        index.updated_at = now

    await db.commit()
    await db.refresh(event)
    return _event_to_dict(event)


def _summarize(events: list[TraceEvent], trace_id: str) -> TraceSummary:
    root = next(
        (
            e
            for e in events
            if e.event_type in ("task_received", "task_started", "hire_started")
        ),
        events[0],
    )
    failed = any(e.event_type in ("task_failed", "hire_failed") for e in events)
    completed = any(
        e.event_type in ("task_completed", "hire_completed") and e.depth == 0 for e in events
    )
    return TraceSummary(
        trace_id=trace_id,
        started_at=events[0].timestamp,
        last_at=events[-1].timestamp,
        root_text=root.text,
        root_agent=root.agent_name,
        event_count=len(events),
        agents=sorted({e.agent_name for e in events if e.agent_name}),
        status="failed" if failed else ("completed" if completed else "working"),
    )


async def list_traces(db: AsyncSession, *, limit: int = 50) -> list[TraceSummary]:
    result = await db.execute(
        select(TraceIndex).order_by(TraceIndex.last_event_at.desc()).limit(limit)
    )
    indices = list(result.scalars().all())
    summaries: list[TraceSummary] = []
    for index in indices:
        ev_result = await db.execute(
            select(TraceEvent)
            .where(TraceEvent.trace_id == index.trace_id)
            .order_by(TraceEvent.timestamp.asc())
        )
        events = list(ev_result.scalars().all())
        if events:
            summaries.append(_summarize(events, index.trace_id))
    return summaries


async def get_trace(db: AsyncSession, *, trace_id: str) -> list[dict[str, Any]]:
    result = await db.execute(
        select(TraceEvent)
        .where(TraceEvent.trace_id == trace_id)
        .order_by(TraceEvent.timestamp.asc())
    )
    events = list(result.scalars().all())
    if not events:
        raise LookupError("Trace not found")
    return [_event_to_dict(e) for e in events]
