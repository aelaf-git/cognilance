"""Derive Google Calendar list_events parameters from natural language."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _week_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    week_start = _start_of_day(now - timedelta(days=now.weekday()))
    week_end = week_start + timedelta(days=7)
    return week_start, week_end


def prepare_calendar_list_params(query: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fill time_min/time_max and defaults for events.list."""
    merged = dict(params or {})
    q_lower = query.lower()
    now = datetime.now(timezone.utc)

    if not merged.get("time_min"):
        if "this week" in q_lower or ("week" in q_lower and "next week" not in q_lower):
            start, end = _week_bounds(now)
            merged["time_min"] = _to_rfc3339(start)
            merged["time_max"] = _to_rfc3339(end)
        elif "next week" in q_lower:
            start, end = _week_bounds(now)
            start += timedelta(days=7)
            end += timedelta(days=7)
            merged["time_min"] = _to_rfc3339(start)
            merged["time_max"] = _to_rfc3339(end)
        elif "today" in q_lower:
            start = _start_of_day(now)
            merged["time_min"] = _to_rfc3339(start)
            merged["time_max"] = _to_rfc3339(start + timedelta(days=1))
        elif "tomorrow" in q_lower:
            start = _start_of_day(now + timedelta(days=1))
            merged["time_min"] = _to_rfc3339(start)
            merged["time_max"] = _to_rfc3339(start + timedelta(days=1))
        else:
            merged["time_min"] = _to_rfc3339(now)

    if not merged.get("time_max") and "time_min" in merged:
        # Default window: 14 days ahead when only time_min was set explicitly
        if "time_max" not in (params or {}):
            try:
                start = datetime.fromisoformat(str(merged["time_min"]).replace("Z", "+00:00"))
                merged.setdefault("time_max", _to_rfc3339(start + timedelta(days=14)))
            except ValueError:
                merged.setdefault("time_max", _to_rfc3339(now + timedelta(days=14)))

    merged.setdefault("max_results", 25)
    return merged
