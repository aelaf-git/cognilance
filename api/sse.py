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


def sse_line(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def sse_response(
    stream: AsyncIterator[str], *, extra_headers: dict[str, str] | None = None
) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={**SSE_HEADERS, **(extra_headers or {})},
    )
