"""Finalize session status after a graph run."""

from __future__ import annotations

from orchestrator.missions.models import Mission, MissionStatus
from orchestrator.missions.session_type import SessionType
from orchestrator.missions.store import MissionStore
from orchestrator.subscriptions.models import SubscriptionStatus
from orchestrator.subscriptions.store import SubscriptionStore


def finalize_session_status(
    store: MissionStore,
    mission: Mission,
    *,
    had_error: bool,
    error_message: str | None,
    final_text: str | None,
    final_ui: list | None,
    sub_store: SubscriptionStore | None = None,
) -> None:
    # User abort wins — never overwrite a cancelled session with completed/failed.
    current = store.get_mission(mission.id) or mission
    if current.status == MissionStatus.CANCELLED:
        return

    subs = sub_store or SubscriptionStore()
    active_sub = subs.get_by_mission_id(mission.id)
    listener_active = bool(
        active_sub and active_sub.status == SubscriptionStatus.ACTIVE
    )

    if had_error:
        store.update_status(mission.id, MissionStatus.FAILED, error=error_message)
        return

    if listener_active or mission.session_type == SessionType.RECURRING:
        store.update_status(
            mission.id,
            MissionStatus.RUNNING,
            result_text=final_text,
            result_ui=final_ui,
        )
        store.append_event(
            mission.id,
            {"event": "run_completed", "text": final_text, "status": "running"},
        )
        return

    store.update_status(
        mission.id,
        MissionStatus.COMPLETED,
        result_text=final_text,
        result_ui=final_ui,
    )
