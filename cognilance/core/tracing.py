"""TraceEmitter — fire-and-forget trace events to the registry collector."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from cognilance.core.models import TraceEvent

logger = logging.getLogger(__name__)


class TraceEmitter:
    """
    Sends TraceEvents to the registry (`POST /v1/traces/events`).

    Emission is best-effort: failures are logged at debug level and never
    interrupt agent work.
    """

    def __init__(self, *, registry_url: str, api_key: str | None = None) -> None:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=registry_url.rstrip("/"),
            headers=headers,
            timeout=5.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def emit(self, **fields: Any) -> None:
        event = TraceEvent(**fields)
        try:
            await self._client.post("/v1/traces/events", json=event.model_dump(mode="json"))
        except Exception:
            logger.debug("Trace event emission failed", exc_info=True)

    def emit_nowait(self, **fields: Any) -> None:
        """Schedule an emit on the running loop without awaiting it."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.emit(**fields))
