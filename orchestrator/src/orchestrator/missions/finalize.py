"""Finalize session status after a graph run."""

from __future__ import annotations

from orchestrator.missions.models import Mission, MissionStatus
from orchestrator.missions.session_type import SessionType
from orchestrator.missions.store import MissionStore


def finalize_session_status(
    store: MissionStore,
    mission: Mission,
    *,
    had_error: bool,
    error_message: str | None,
    final_text: str | None,
    final_ui: list | None,
) -> None:
    if had_error:
        store.update_status(mission.id, MissionStatus.FAILED, error=error_message)
        return

    if mission.session_type == SessionType.RECURRING:
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
