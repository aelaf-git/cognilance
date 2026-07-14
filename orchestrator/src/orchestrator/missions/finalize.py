"""Finalize session status after a graph run."""

from __future__ import annotations

import logging

from cognilance.payments import EscrowStatus, PaymentService

from orchestrator.missions.models import Mission, MissionStatus
from orchestrator.missions.session_type import SessionType
from orchestrator.missions.store import MissionStore
from orchestrator.subscriptions.models import SubscriptionStatus
from orchestrator.subscriptions.store import SubscriptionStore

logger = logging.getLogger(__name__)


def _settle_or_refund_mission(mission_id: str, *, settle: bool) -> None:
    """Release (settle) or refund every funded escrow for this mission."""
    try:
        payments = PaymentService()
    except Exception:
        logger.exception("PaymentService init failed during finalize")
        return
    for hire in payments.list_mission_escrows(mission_id):
        if hire.status != EscrowStatus.FUNDED:
            continue
        try:
            if settle:
                payments.release_escrow(hire.hire_id)
                logger.info("Settled escrow %s for mission %s", hire.hire_id, mission_id)
            else:
                payments.refund_escrow(hire.hire_id)
                logger.info("Refunded escrow %s for mission %s", hire.hire_id, mission_id)
        except Exception:
            logger.exception(
                "Failed to %s escrow %s",
                "settle" if settle else "refund",
                hire.hire_id,
            )


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
        _settle_or_refund_mission(mission.id, settle=False)
        return

    subs = sub_store or SubscriptionStore()
    active_sub = subs.get_by_mission_id(mission.id)
    listener_active = bool(
        active_sub and active_sub.status == SubscriptionStatus.ACTIVE
    )

    if had_error:
        store.update_status(mission.id, MissionStatus.FAILED, error=error_message)
        _settle_or_refund_mission(mission.id, settle=False)
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
        # Recurring: settle this run's funded hires so agents get paid per cycle.
        _settle_or_refund_mission(mission.id, settle=True)
        return

    store.update_status(
        mission.id,
        MissionStatus.COMPLETED,
        result_text=final_text,
        result_ui=final_ui,
    )
    _settle_or_refund_mission(mission.id, settle=True)
