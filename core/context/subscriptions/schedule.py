"""Admin-created weekly report schedules. Phrase matching is not used."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from core.context.orgs.store import OrgStore
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.timezone import (
    deployment_default_timezone,
    get_stored_user_timezone,
    normalize_timezone_name,
)
from core.runtime.missions.session_type import SessionType
from core.runtime.missions.store import MissionStore

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def parse_weekday(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Invalid weekday")
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 6:
        return value
    text = str(value if value is not None else "").strip().lower()
    if text.isdigit():
        number = int(text)
        if 0 <= number <= 6:
            return number
    if text in _WEEKDAYS:
        return _WEEKDAYS[text]
    raise ValueError("Invalid weekday")


def parse_hour(value: Any) -> int:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Invalid hour")
    try:
        hour = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid hour") from exc
    if hour < 0 or hour > 23:
        raise ValueError("Invalid hour")
    return hour


def next_weekly_utc(
    *,
    weekday: int,
    hour: int,
    timezone_name: str,
    now: datetime | None = None,
) -> datetime:
    """Next local weekday and hour, as UTC. The current slot is due immediately."""
    zone = ZoneInfo(timezone_name)
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local_now = moment.astimezone(zone)
    candidate = local_now.replace(hour=hour, minute=0, second=0, microsecond=0)
    days_ahead = (weekday - candidate.weekday()) % 7
    candidate = candidate + timedelta(days=days_ahead)
    if candidate < local_now:
        candidate += timedelta(days=7)
    return candidate.astimezone(timezone.utc)


def resolve_schedule_timezone(
    payload: dict[str, Any],
    *,
    organization_id: str,
    user_id: str,
    org_store: OrgStore,
) -> str:
    raw = payload.get("timezone")
    if raw not in (None, ""):
        chosen = normalize_timezone_name(str(raw))
        if not chosen:
            raise ValueError("Invalid timezone")
    else:
        chosen = (
            normalize_timezone_name(org_store.get_timezone(organization_id))
            or get_stored_user_timezone(user_id)
            or deployment_default_timezone()
        )
    org_store.set_timezone(organization_id, chosen)
    return chosen


def create_weekly_schedule(
    *,
    organization_id: str,
    user_id: str,
    payload: dict[str, Any],
    org_store: OrgStore,
    sub_store: SubscriptionStore,
    mission_store: MissionStore,
    now: datetime | None = None,
) -> dict[str, Any]:
    pipeline = str(payload.get("pipeline") or "").strip()
    if pipeline != "weekly_report":
        raise ValueError("Unsupported pipeline")
    weekday = parse_weekday(payload.get("weekday"))
    hour = parse_hour(payload.get("hour"))
    project_raw = payload.get("project_id")
    project_id = str(project_raw).strip() if project_raw not in (None, "") else None
    zone = resolve_schedule_timezone(
        payload,
        organization_id=organization_id,
        user_id=user_id,
        org_store=org_store,
    )
    config = {
        "pipeline": "weekly_report",
        "weekday": weekday,
        "hour": hour,
        "timezone": zone,
        "project_id": project_id,
    }
    instruction = "Weekly report" if not project_id else f"Weekly report for project {project_id}"
    mission_store.init_db()
    mission = mission_store.create_mission(
        instruction=instruction,
        session_type=SessionType.RECURRING,
        user_id=user_id,
        organization_id=organization_id,
    )
    sub_store.init_db()
    sub = sub_store.create_subscription(
        user_id=user_id,
        conversation_id="",
        integration="schedule",
        kind="weekly_report",
        config=config,
        cursor={"run_count": 0},
        created_from_mission_id=mission.id,
        organization_id=organization_id,
        next_check_at=next_weekly_utc(weekday=weekday, hour=hour, timezone_name=zone, now=now),
    )
    return {
        "subscription_id": sub.id,
        "session_id": mission.id,
        "organization_id": organization_id,
        "status": sub.status.value,
        "config": config,
        "timezone": zone,
        "next_check_at": sub.next_check_at.isoformat(),
    }
