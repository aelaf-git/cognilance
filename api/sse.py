"""Server-sent events helpers."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from fastapi.responses import StreamingResponse

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse_line(event: dict[str, Any], *, event_id: int | str | None = None) -> str:
    body = dict(event)
    body.pop("_event_id", None)
    prefix = f"id: {event_id}\n" if event_id is not None else ""
    return f"{prefix}data: {json.dumps(body)}\n\n"


def event_cursor(event: dict[str, Any]) -> str | None:
    name = str(event.get("event") or "")
    if name == "message" and event.get("id") is not None:
        return f"message:{event['id']}"
    if name == "notification" and event.get("id") is not None:
        return f"notification:{event['id']}"
    if event.get("_event_id") is not None:
        return f"mission:{event['_event_id']}"
    return None


def sse_event_id(event: dict[str, Any]) -> int | str | None:
    name = str(event.get("event") or "")
    if name in {"message", "message_removed", "notification"} and event.get("id") is not None:
        return event["id"]
    if event.get("_event_id") is not None:
        return event["_event_id"]
    return None


async def replay_then_live(
    replay: list[dict[str, Any]],
    live: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[str]:
    """Yield stored events, then live ones, skipping anything the replay already sent."""
    seen: set[str] = set()
    for event in replay:
        cursor = event_cursor(event)
        if cursor:
            seen.add(cursor)
        yield sse_line(event, event_id=sse_event_id(event))
    async for event in live:
        cursor = event_cursor(event)
        if cursor and cursor in seen:
            continue
        if cursor:
            seen.add(cursor)
        yield sse_line(event, event_id=sse_event_id(event))


def sse_response(
    stream: AsyncIterator[str], *, extra_headers: dict[str, str] | None = None
) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={**SSE_HEADERS, **(extra_headers or {})},
    )
