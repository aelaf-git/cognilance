"""Mission data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


from orchestrator.missions.session_type import SessionType


class MissionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Mission:
    id: str
    instruction: str
    status: MissionStatus
    thread_id: str
    session_type: SessionType = SessionType.ONCE
    conversation_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    result_text: str | None = None
    result_ui: list[dict[str, Any]] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "instruction": self.instruction,
            "status": self.status.value,
            "session_type": self.session_type.value,
            "thread_id": self.thread_id,
            "conversation_id": self.conversation_id or self.thread_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result_text": self.result_text,
            "result_ui": self.result_ui or [],
            "error": self.error,
        }

    def to_session_dict(self) -> dict[str, Any]:
        """API alias — sessions are persisted as missions internally."""
        data = self.to_dict()
        data["session_id"] = data["id"]
        return data
