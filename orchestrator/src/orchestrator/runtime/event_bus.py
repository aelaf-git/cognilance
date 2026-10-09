"""In-process fan-out event bus for live SSE (persist + subscribe)."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, AsyncIterator


_SENTINEL = object()


class MissionEventBus:
    """Publish/subscribe per mission_id for chat SSE hot path."""

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def attach(self, mission_id: str) -> asyncio.Queue:
        """Register a subscriber queue before the producer starts (avoids races)."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subs[mission_id].append(queue)
        return queue

    def detach(self, mission_id: str, queue: asyncio.Queue) -> None:
        subs = self._subs.get(mission_id, [])
        if queue in subs:
            subs.remove(queue)
        if not subs and mission_id in self._subs:
            del self._subs[mission_id]

    async def publish(self, mission_id: str, event: dict[str, Any]) -> None:
        queues = list(self._subs.get(mission_id, []))
        for queue in queues:
            await queue.put(dict(event))

    async def close(self, mission_id: str) -> None:
        queues = list(self._subs.get(mission_id, []))
        for queue in queues:
            await queue.put(_SENTINEL)

    async def subscribe(self, mission_id: str) -> AsyncIterator[dict[str, Any]]:
        queue = self.attach(mission_id)
        try:
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    break
                yield item  # type: ignore[misc]
        finally:
            self.detach(mission_id, queue)

    async def drain(self, queue: asyncio.Queue) -> AsyncIterator[dict[str, Any]]:
        """Read events from a pre-attached queue until close sentinel."""
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            yield item  # type: ignore[misc]


# Process-wide bus used by chat_stream + runner.
event_bus = MissionEventBus()
