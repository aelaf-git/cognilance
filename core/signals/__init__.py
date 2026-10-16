"""Trace and feedback capture.

Every durable step is persisted to the Run step log and mirrored to the live
stream so UIs and later the improvement loop see the same signal.
"""

from __future__ import annotations

from typing import Any

from core.runtime.runs.store import RunStore
from pipelines.shared.streaming import emit


def record_step(
    run_id: str | None,
    *,
    kind: str,
    text: str = "",
    data: dict[str, Any] | None = None,
    stream: bool = True,
) -> None:
    """Append a step to the Run log and optionally emit a `trace` event."""
    payload = dict(data or {})
    if run_id:
        RunStore().append_step(run_id, kind=kind, text=text, data=payload)
    if stream:
        emit("trace", kind=kind, text=text, run_id=run_id, **payload)


def record_feedback(run_id: str, *, rating: int, note: str = "") -> None:
    """Capture user feedback for a Run (consumed by improvement/ later)."""
    RunStore().append_step(
        run_id,
        kind="feedback",
        text=note,
        data={"rating": int(rating)},
    )
