"""Fire one weekly-report subscription as a schedule Run. No chat message is written."""

from __future__ import annotations

import logging
from datetime import timedelta, timezone
from typing import Any

from core.context.request import current_mission_id, current_user_id
from core.context.subscriptions.models import Subscription
from core.context.subscriptions.store import SubscriptionStore
from core.runtime.runs.models import RunStatus, RunTrigger
from core.runtime.runs.store import RunStore

logger = logging.getLogger(__name__)


async def run_weekly_report_graph(*, instruction: str, run_id: str, user_id: str) -> None:
    from langchain_core.messages import HumanMessage

    from pipelines.weekly_report.graph import ensure_graph

    graph = await ensure_graph(with_checkpointer=False)
    await graph.ainvoke(
        {"messages": [HumanMessage(content=instruction)], "run_id": run_id},
        config={"configurable": {"thread_id": run_id}},
    )


def _instruction(sub: Subscription) -> str:
    project_id = str(sub.config.get("project_id") or "").strip()
    if project_id:
        return f"Weekly report for project {project_id}"
    return "Weekly report"


async def fire_weekly_report(
    sub: Subscription,
    *,
    store: SubscriptionStore | None = None,
) -> dict[str, Any]:
    subs = store or SubscriptionStore()
    if sub.status.value == "paused":
        return {"ran": False, "skipped": "paused"}
    runs = RunStore()
    runs.init_db()
    instruction = _instruction(sub)
    run = runs.create_run(
        instruction=instruction,
        thread_id=f"schedule:{sub.id}",
        trigger=RunTrigger.SCHEDULE,
        user_id=sub.user_id,
        organization_id=sub.organization_id,
        mission_id=sub.created_from_mission_id,
    )
    runs.update_status(run.id, RunStatus.RUNNING)
    user_token = current_user_id.set(sub.user_id or "")
    mission_token = current_mission_id.set(run.id)
    try:
        await run_weekly_report_graph(
            instruction=instruction,
            run_id=run.id,
            user_id=sub.user_id or "",
        )
    except Exception as exc:
        message = str(exc)[:500] or "Weekly report failed"
        logger.exception("Weekly report failed for subscription %s", sub.id)
        runs.update_status(run.id, RunStatus.FAILED, error=message)
        subs.set_error(sub.id, message)
        return {"ran": False, "run_id": run.id, "error": message}
    finally:
        current_user_id.reset(user_token)
        current_mission_id.reset(mission_token)
    runs.update_status(run.id, RunStatus.COMPLETED, result_text=instruction)
    nxt = sub.next_check_at
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=timezone.utc)
    subs.reschedule(sub.id, nxt + timedelta(days=7))
    return {"ran": True, "run_id": run.id}
