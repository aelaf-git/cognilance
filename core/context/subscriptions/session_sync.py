"""Keep mission (session) tickets aligned with background subscriptions."""

from __future__ import annotations

from typing import Any

from core.runtime.missions.models import Mission, MissionStatus
from core.runtime.missions.session_type import SessionType
from core.runtime.missions.store import MissionStore
from core.context.subscriptions.models import Subscription, SubscriptionStatus
from core.context.subscriptions.store import SubscriptionStore


def enrich_session_dict(
    mission: Mission,
    *,
    sub_store: SubscriptionStore | None = None,
) -> dict[str, Any]:
    """Attach listener metadata so the UI can show one session ticket per listener."""
    store = sub_store or SubscriptionStore()
    data = mission.to_session_dict()
    sub = store.get_by_mission_id(mission.id)
    listener_active = bool(sub and sub.status == SubscriptionStatus.ACTIVE)
    data["subscription_id"] = sub.id if sub else None
    data["listener_active"] = listener_active
    if sub:
        data["listener_integration"] = sub.integration
        data["listener_kind"] = sub.kind

    if listener_active:
        data["display_status"] = "processing"
    elif mission.session_type == SessionType.ONCE and mission.status == MissionStatus.COMPLETED:
        data["display_status"] = "done"
    elif mission.status == MissionStatus.CANCELLED:
        data["display_status"] = "aborted"
    elif mission.status == MissionStatus.FAILED:
        data["display_status"] = "failed"
    elif mission.status == MissionStatus.COMPLETED:
        data["display_status"] = "done"
    else:
        data["display_status"] = mission.status.value
    return data


def cancel_mission_for_subscription(
    sub: Subscription,
    *,
    mission_store: MissionStore | None = None,
    error: str = "Stopped by user",
) -> None:
    if not sub.created_from_mission_id:
        return
    store = mission_store or MissionStore()
    mission = store.get_mission(sub.created_from_mission_id)
    if not mission:
        return
    if mission.status in {MissionStatus.RUNNING, MissionStatus.QUEUED}:
        store.update_status(sub.created_from_mission_id, MissionStatus.CANCELLED, error=error)
        store.append_event(sub.created_from_mission_id, {"event": "session_aborted"})


def stop_listener_for_mission(
    mission_id: str,
    *,
    sub_store: SubscriptionStore | None = None,
    mission_store: MissionStore | None = None,
) -> bool:
    """Abort a long-running session by stopping its linked subscription."""
    subs = sub_store or SubscriptionStore()
    missions = mission_store or MissionStore()
    stopped = subs.stop_by_mission_id(mission_id)
    mission = missions.get_mission(mission_id)
    if mission and mission.status in {MissionStatus.RUNNING, MissionStatus.QUEUED}:
        missions.update_status(mission_id, MissionStatus.CANCELLED, error="Aborted by user")
        missions.append_event(mission_id, {"event": "session_aborted"})
        return True
    return stopped


def start_listener_for_mission(
    mission_id: str,
    *,
    sub_store: SubscriptionStore | None = None,
    mission_store: MissionStore | None = None,
) -> bool:
    """Resume a long-running session by reactivating its linked subscription."""
    subs = sub_store or SubscriptionStore()
    missions = mission_store or MissionStore()
    mission = missions.get_mission(mission_id)
    if not mission:
        return False
    if mission.session_type != SessionType.RECURRING:
        return False
    sub = subs.get_by_mission_id(mission_id)
    if not sub:
        return False
    if not subs.reactivate(sub.id):
        return False
    missions.update_status(mission_id, MissionStatus.RUNNING, error=None)
    missions.append_event(mission_id, {"event": "session_started", "reason": "user"})
    return True
