"""Current date/time for the orchestrator and built-in time tool."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from orchestrator.users.timezone import resolve_user_timezone_name


def resolve_timezone(
    name: str | None = None,
    *,
    user_id: str | None = None,
) -> ZoneInfo:
    """Resolve a ZoneInfo for the user; always falls back safely to UTC."""
    tz_name = resolve_user_timezone_name(user_id=user_id, explicit=name)
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def user_now(*, user_id: str | None = None, tz: str | None = None) -> datetime:
    """Current instant in the user's local timezone."""
    zone = resolve_timezone(tz, user_id=user_id)
    return datetime.now(timezone.utc).astimezone(zone)


def current_time_context(
    *,
    user_id: str | None = None,
    tz: str | None = None,
) -> dict[str, Any]:
    """
    Return structured current time in UTC and the user's local timezone.

    The server clock is the source of truth. Local timezone comes from the user's
    browser (stored per user_id), with UTC as the deployment-safe fallback.
    """
    zone = resolve_timezone(tz, user_id=user_id)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(zone)
    week_start = now_local.date() - timedelta(days=now_local.weekday())

    return {
        "utc_iso": now_utc.isoformat().replace("+00:00", "Z"),
        "local_iso": now_local.isoformat(),
        "timezone": str(zone),
        "weekday": now_local.strftime("%A"),
        "date": now_local.strftime("%Y-%m-%d"),
        "time": now_local.strftime("%H:%M"),
        "year": now_local.year,
        "month": now_local.month,
        "day": now_local.day,
        "hour": now_local.hour,
        "minute": now_local.minute,
        "unix_timestamp": int(now_utc.timestamp()),
        "week_start_date": week_start.isoformat(),
        "is_weekend": now_local.weekday() >= 5,
    }


def format_current_time_summary(
    ctx: dict[str, Any] | None = None,
    *,
    user_id: str | None = None,
    tz: str | None = None,
) -> str:
    """Human-readable one-liner for chat or tool results."""
    data = ctx or current_time_context(user_id=user_id, tz=tz)
    return (
        f"It is {data['weekday']}, {data['date']} at {data['time']} "
        f"in your timezone ({data['timezone']}). UTC: {data['utc_iso']}."
    )


def time_context_for_planner(*, user_id: str | None = None) -> str:
    """Short block injected into planner / capabilities prompts."""
    ctx = current_time_context(user_id=user_id)
    return (
        f"User's local time: {ctx['weekday']}, {ctx['date']} {ctx['time']} ({ctx['timezone']}); "
        f"UTC {ctx['utc_iso']}; week starts {ctx['week_start_date']} (in user's timezone)."
    )
