"""Durable Run models: a run is a job, not a chat reply."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RunTrigger(str, Enum):
    MESSAGE = "message"
    SCHEDULE = "schedule"
    EVENT = "event"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Run:
    id: str
    instruction: str
    status: RunStatus
    trigger: RunTrigger
    thread_id: str
    conversation_id: str | None = None
    user_id: str | None = None
    mission_id: str | None = None  # legacy session alias when bridged
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    result_text: str | None = None
    result_ui: list[dict[str, Any]] | None = None
    error: str | None = None
    pending_approval: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "instruction": self.instruction,
            "status": self.status.value,
            "trigger": self.trigger.value,
            "thread_id": self.thread_id,
            "conversation_id": self.conversation_id or self.thread_id,
            "user_id": self.user_id,
            "mission_id": self.mission_id or self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result_text": self.result_text,
            "result_ui": self.result_ui or [],
            "error": self.error,
            "pending_approval": self.pending_approval,
        }


@dataclass
class RunStep:
    id: str
    run_id: str
    kind: str  # node_entered | task_created | task_claimed | task_done | tool_call | approval
    text: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "kind": self.kind,
            "text": self.text,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
        }
