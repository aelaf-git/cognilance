"""Subscription models for long-running integration listeners."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class Subscription:
    id: str
    user_id: str
    conversation_id: str
    integration: str
    kind: str
    config: dict[str, Any]
    cursor: dict[str, Any]
    status: SubscriptionStatus
    next_check_at: datetime
    created_at: datetime
    updated_at: datetime
    created_from_mission_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "integration": self.integration,
            "kind": self.kind,
            "config": self.config,
            "cursor": self.cursor,
            "status": self.status.value,
            "next_check_at": self.next_check_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_from_mission_id": self.created_from_mission_id,
            "error": self.error,
        }
