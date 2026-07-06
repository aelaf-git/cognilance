"""Whether a session can be hidden from the UI (soft dismiss)."""

from __future__ import annotations

from orchestrator.missions.models import Mission, MissionStatus
from orchestrator.missions.session_type import SessionType


def can_hide_session(mission: Mission) -> bool:
    """Active / unaborted sessions cannot be dismissed from the sidebar."""
    if mission.status in {MissionStatus.RUNNING, MissionStatus.QUEUED}:
        return False
    if mission.session_type == SessionType.RECURRING:
        return mission.status in {MissionStatus.CANCELLED, MissionStatus.FAILED}
    return mission.status in {
        MissionStatus.COMPLETED,
        MissionStatus.FAILED,
        MissionStatus.CANCELLED,
    }
