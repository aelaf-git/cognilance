"""Detect scheduled / recurring background task requests."""

from __future__ import annotations

import re

from orchestrator.subscriptions.monitor_intent import is_monitor_request

_RECURRING_TASK_HINTS = (
    "every day",
    "each day",
    "daily",
    "every week",
    "each week",
    "weekly",
    "every hour",
    "each hour",
    "hourly",
    "every morning",
    "every evening",
    "every night",
    "on a schedule",
    "run this every",
    "do this every",
    "repeat every",
    "recurring task",
    "background task",
    "automate",
    "automation",
    "scheduled task",
)

_STOP_RECURRING_HINTS = (
    "stop recurring",
    "stop automation",
    "stop scheduled",
    "stop the schedule",
    "stop background task",
    "cancel recurring",
    "cancel automation",
    "cancel scheduled",
    "end recurring",
    "no longer run",
    "don't run this every",
    "do not run this every",
)


def is_stop_recurring_request(query: str) -> bool:
    q = query.lower().strip()
    return any(hint in q for hint in _STOP_RECURRING_HINTS)


def is_recurring_task_request(query: str) -> bool:
    """True when the user wants a task re-run on an interval (not event listening)."""
    if is_monitor_request(query):
        return False
    if is_stop_recurring_request(query):
        return False
    lower = query.lower()
    return any(hint in lower for hint in _RECURRING_TASK_HINTS)


def extract_task_instruction(query: str) -> str:
    """Strip scheduling boilerplate to get the task body."""
    text = query.strip()
    patterns = [
        r"^(?:please\s+)?(?:every\s+day|daily|each\s+day)[,\s]+",
        r"^(?:please\s+)?(?:every\s+week|weekly|each\s+week)[,\s]+",
        r"^(?:please\s+)?(?:every\s+hour|hourly|each\s+hour)[,\s]+",
        r"^(?:please\s+)?(?:every\s+morning|every\s+evening|every\s+night)[,\s]+",
        r"^(?:please\s+)?(?:run|do|execute|perform)\s+this\s+(?:every\s+\w+)[,\s:]+",
        r"^(?:please\s+)?(?:automate|schedule|repeat)\s+",
        r"^(?:please\s+)?on\s+a\s+schedule[,\s:]+",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).strip()
    return text or query.strip()
