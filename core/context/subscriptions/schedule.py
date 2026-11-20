"""Organization schedules. A cadence says when; an action says what runs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from core.context.orgs.store import OrgStore
from core.context.subscriptions.models import Subscription
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.timezone import (
    deployment_default_timezone,
    get_stored_user_timezone,
    normalize_timezone_name,
)
from core.runtime.missions.session_type import SessionType
from core.runtime.missions.store import MissionStore

PIPELINES = frozenset({"weekly_report", "concept_note", "email_followup"})
_TITLES = {
    "weekly_report": "Weekly report",
    "concept_note": "Concept note",
    "email_followup": "Email follow-up",
}
_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_MIN_INTERVAL_SECONDS = 300


def parse_weekday(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Invalid weekday")
    if isinstance(value, int) and 0 <= value <= 6:
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


def parse_every_seconds(value: Any) -> int:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Invalid interval")
    try:
        seconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid interval") from exc
    if seconds < _MIN_INTERVAL_SECONDS:
        raise ValueError("Invalid interval")
    return seconds


def _blank(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def next_weekly_utc(
    *,
    weekday: int,
    hour: int,
    timezone_name: str,
    now: datetime | None = None,
) -> datetime:
    """Next local weekday and hour, as UTC. The current slot is due immediately."""
    zone = ZoneInfo(timezone_name)
    local_now = _aware(now or datetime.now(timezone.utc)).astimezone(zone)
    candidate = local_now.replace(hour=hour, minute=0, second=0, microsecond=0)
    days_ahead = (weekday - candidate.weekday()) % 7
    candidate = candidate + timedelta(days=days_ahead)
    if candidate < local_now:
        candidate += timedelta(days=7)
    return candidate.astimezone(timezone.utc)


def next_daily_utc(*, hour: int, timezone_name: str, now: datetime | None = None) -> datetime:
    zone = ZoneInfo(timezone_name)
    local_now = _aware(now or datetime.now(timezone.utc)).astimezone(zone)
    candidate = local_now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate < local_now:
        candidate += timedelta(days=1)
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


def _pipeline_action(raw: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("pipeline") or "").strip()
    if name not in PIPELINES:
        raise ValueError("Unsupported pipeline")
    return {
        "type": "pipeline",
        "pipeline": name,
        "project_id": _blank(raw.get("project_id")),
        "instruction": _blank(raw.get("instruction")),
    }


def _action_from(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Invalid action")
    kind = str(raw.get("type") or "").strip()
    if kind == "instruction":
        text = _blank(raw.get("instruction"))
        if not text:
            raise ValueError("Instruction is required")
        return {"type": "instruction", "instruction": text}
    if kind == "pipeline":
        return _pipeline_action(raw)
    raise ValueError("Invalid action")


def _cadence_from(raw: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    cadence_type = str(raw.get("type") or "").strip()
    if cadence_type == "weekly":
        return {
            "type": "weekly",
            "weekday": parse_weekday(raw.get("weekday", payload.get("weekday"))),
            "hour": parse_hour(raw.get("hour", payload.get("hour"))),
        }
    if cadence_type == "daily":
        return {"type": "daily", "hour": parse_hour(raw.get("hour", payload.get("hour")))}
    if cadence_type == "interval":
        return {"type": "interval", "every_seconds": parse_every_seconds(raw.get("every_seconds"))}
    raise ValueError("Invalid cadence")


def schedule_parts(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return cadence, action, and the payload used to resolve a timezone."""
    nested = payload.get("cadence")
    if isinstance(nested, dict):
        cadence = _cadence_from(nested, payload)
        zone_source = dict(payload)
        if nested.get("timezone") not in (None, ""):
            zone_source["timezone"] = nested.get("timezone")
        action_raw = payload.get("action")
        if action_raw is None and payload.get("pipeline"):
            action_raw = {
                "type": "pipeline",
                "pipeline": payload.get("pipeline"),
                "project_id": payload.get("project_id"),
                "instruction": payload.get("instruction"),
            }
        return cadence, _action_from(action_raw), zone_source
    cadence = {
        "type": "weekly",
        "weekday": parse_weekday(payload.get("weekday")),
        "hour": parse_hour(payload.get("hour")),
    }
    action = _pipeline_action(payload)
    return cadence, action, payload


def schedule_instruction(action: dict[str, Any]) -> str:
    if action.get("type") == "instruction":
        return str(action.get("instruction") or "").strip()
    custom = _blank(action.get("instruction"))
    if custom:
        return custom
    title = _TITLES.get(str(action.get("pipeline") or ""), "Scheduled run")
    project_id = _blank(action.get("project_id"))
    if project_id:
        return f"{title} for project {project_id}"
    return title


def next_check_at(
    cadence: dict[str, Any],
    timezone_name: str,
    now: datetime | None = None,
) -> datetime:
    moment = _aware(now or datetime.now(timezone.utc))
    if cadence.get("type") == "interval":
        return moment + timedelta(seconds=int(cadence["every_seconds"]))
    if cadence.get("type") == "daily":
        return next_daily_utc(hour=int(cadence["hour"]), timezone_name=timezone_name, now=moment)
    return next_weekly_utc(
        weekday=int(cadence["weekday"]),
        hour=int(cadence["hour"]),
        timezone_name=timezone_name,
        now=moment,
    )


def advance_check(cadence: dict[str, Any], previous: datetime) -> datetime:
    moment = _aware(previous)
    if cadence.get("type") == "daily":
        return moment + timedelta(days=1)
    if cadence.get("type") == "interval":
        return moment + timedelta(seconds=int(cadence.get("every_seconds") or _MIN_INTERVAL_SECONDS))
    return moment + timedelta(days=7)


def normalize_schedule(sub: Subscription) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read a current schedule or an older flat weekly-report config."""
    config = sub.config or {}
    cadence = config.get("cadence")
    action = config.get("action")
    if isinstance(cadence, dict) and isinstance(action, dict):
        return cadence, action
    return (
        {
            "type": "weekly",
            "weekday": int(config.get("weekday") or 0),
            "hour": int(config.get("hour") or 0),
            "timezone": config.get("timezone") or "UTC",
        },
        {
            "type": "pipeline",
            "pipeline": str(config.get("pipeline") or "weekly_report"),
            "project_id": _blank(config.get("project_id")),
            "instruction": _blank(config.get("instruction")),
        },
    )


def create_schedule(
    *,
    organization_id: str,
    user_id: str,
    payload: dict[str, Any],
    org_store: OrgStore,
    sub_store: SubscriptionStore,
    mission_store: MissionStore,
    now: datetime | None = None,
) -> dict[str, Any]:
    cadence, action, zone_source = schedule_parts(payload)
    zone = resolve_schedule_timezone(
        zone_source,
        organization_id=organization_id,
        user_id=user_id,
        org_store=org_store,
    )
    cadence = {**cadence, "timezone": zone}
    config = {"cadence": cadence, "action": action}
    instruction = schedule_instruction(action)
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
        kind="schedule",
        config=config,
        cursor={"run_count": 0},
        created_from_mission_id=mission.id,
        organization_id=organization_id,
        next_check_at=next_check_at(cadence, zone, now=now),
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


create_weekly_schedule = create_schedule
