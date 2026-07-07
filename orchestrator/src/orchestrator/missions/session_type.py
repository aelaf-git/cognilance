"""Session scheduling — one-shot vs recurring."""

from __future__ import annotations

from enum import Enum

from orchestrator.subscriptions.monitor_intent import is_monitor_request

_RECURRING_HINTS = (
    "weekly",
    "every week",
    "each week",
    "daily",
    "every day",
    "each day",
    "monthly",
    "schedule",
    "scheduled",
    "recurring",
    "repeat",
    "automate",
    "automation",
    "cron",
    "ongoing",
    "until i stop",
    "until aborted",
)


class SessionType(str, Enum):
    ONCE = "once"
    RECURRING = "recurring"


def detect_session_type(instruction: str) -> SessionType:
    if is_monitor_request(instruction):
        return SessionType.RECURRING
    lower = instruction.lower()
    if any(hint in lower for hint in _RECURRING_HINTS):
        return SessionType.RECURRING
    return SessionType.ONCE
