"""Parse interval and params for recurring background tasks."""

from __future__ import annotations

import re
from typing import Any

from orchestrator.subscriptions.recurring_intent import extract_task_instruction

MIN_INTERVAL_SECONDS = 300  # 5 minutes
DEFAULT_INTERVAL_SECONDS = 86_400  # daily


def parse_poll_interval_seconds(query: str, override: int | None = None) -> int:
    if override is not None and override >= MIN_INTERVAL_SECONDS:
        return int(override)

    q = query.lower()

    every_n = re.search(
        r"every\s+(\d+)\s*(second|seconds|sec|s|minute|minutes|min|hour|hours|hr|h|day|days|week|weeks)\b",
        q,
    )
    if every_n:
        amount = int(every_n.group(1))
        unit = every_n.group(2)
        if unit.startswith("sec") or unit == "s":
            seconds = amount
        elif unit.startswith("min"):
            seconds = amount * 60
        elif unit.startswith("h") or unit == "hr":
            seconds = amount * 3600
        elif unit.startswith("week"):
            seconds = amount * 604_800
        else:
            seconds = amount * 86_400
        return max(MIN_INTERVAL_SECONDS, seconds)

    if "every hour" in q or "hourly" in q or "each hour" in q:
        return 3600
    if "every week" in q or "weekly" in q or "each week" in q:
        return 604_800
    if (
        "every day" in q
        or "daily" in q
        or "each day" in q
        or "every morning" in q
        or "every evening" in q
        or "every night" in q
    ):
        return 86_400

    return DEFAULT_INTERVAL_SECONDS


def format_interval(seconds: int) -> str:
    if seconds % 604_800 == 0 and seconds >= 604_800:
        weeks = seconds // 604_800
        return f"{weeks} week" if weeks == 1 else f"{weeks} weeks"
    if seconds % 86_400 == 0 and seconds >= 86_400:
        days = seconds // 86_400
        return f"{days} day" if days == 1 else f"{days} days"
    if seconds % 3600 == 0 and seconds >= 3600:
        hours = seconds // 3600
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    if seconds % 60 == 0 and seconds >= 60:
        minutes = seconds // 60
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return f"{seconds} seconds"


def prepare_recurring_subscribe_params(
    query: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(params or {})
    interval = parse_poll_interval_seconds(
        query,
        int(merged["poll_interval_seconds"]) if merged.get("poll_interval_seconds") else None,
    )
    instruction = str(merged.get("instruction") or extract_task_instruction(query)).strip()
    if not instruction:
        instruction = query.strip()
    merged["instruction"] = instruction
    merged["poll_interval_seconds"] = interval
    return merged
