"""Shared task board models — specialists claim structured work, not free chat."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BoardTaskStatus(str, Enum):
    OPEN = "open"
    CLAIMED = "claimed"
    DONE = "done"
    FAILED = "failed"


def specialist_roles() -> frozenset[str]:
    """Specialist ids from agents/*/agent.yaml (excludes the coordinator)."""
    from agents.loader import specialist_ids

    return frozenset(specialist_ids())


class _SpecialistRoles:
    """Lazy set view kept for ``SPECIALIST_ROLES`` imports."""

    def __contains__(self, item: object) -> bool:
        from agents.loader import normalize_role_id

        return normalize_role_id(str(item)) in specialist_roles()

    def __iter__(self):
        return iter(specialist_roles())

    def __len__(self) -> int:
        return len(specialist_roles())


SPECIALIST_ROLES = _SpecialistRoles()


@dataclass
class BoardTask:
    id: str
    run_id: str
    title: str
    instruction: str
    assignee_role: str
    status: BoardTaskStatus = BoardTaskStatus.OPEN
    depends_on: list[str] = field(default_factory=list)
    result_json: dict[str, Any] = field(default_factory=dict)
    result_text: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "title": self.title,
            "instruction": self.instruction,
            "assignee_role": self.assignee_role,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "result_json": self.result_json,
            "result_text": self.result_text,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
