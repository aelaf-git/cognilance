"""Fire one organization schedule as a Run. The cadence decides the next time."""

from __future__ import annotations

import logging
from typing import Any

from core.context.request import current_mission_id, current_user_id
from core.context.subscriptions.models import Subscription
from core.context.subscriptions.schedule import (
    PIPELINES,
    advance_check,
    normalize_schedule,
    schedule_instruction,
)
from core.context.subscriptions.store import SubscriptionStore
from core.runtime.runs.models import RunStatus, RunTrigger
from core.runtime.runs.store import RunStore
from workers.schedulers.recurring_runner import run_recurring_instruction

logger = logging.getLogger(__name__)


async def run_pipeline_graph(
    *,
    pipeline: str,
    instruction: str,
    run_id: str,
    user_id: str,
) -> None:
    import importlib

    from langchain_core.messages import HumanMessage

    if pipeline not in PIPELINES:
        raise ValueError("Unsupported pipeline")
    module = importlib.import_module(f"pipelines.{pipeline}.graph")
    graph = await module.ensure_graph(with_checkpointer=False)
    await graph.ainvoke(
        {"messages": [HumanMessage(content=instruction)], "run_id": run_id},
        config={"configurable": {"thread_id": run_id}},
    )


def _fail(store: SubscriptionStore, sub: Subscription, run_id: str | None, message: str) -> dict[str, Any]:
    if run_id:
        RunStore().update_status(run_id, RunStatus.FAILED, error=message)
    store.set_error(sub.id, message)
    return {"ran": False, "run_id": run_id, "error": message}


async def _fire_pipeline(
    sub: Subscription,
    action: dict[str, Any],
    store: SubscriptionStore,
) -> dict[str, Any]:
    instruction = schedule_instruction(action)
    runs = RunStore()
    runs.init_db()
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
        await run_pipeline_graph(
            pipeline=str(action.get("pipeline") or ""),
            instruction=instruction,
            run_id=run.id,
            user_id=sub.user_id or "",
        )
    except Exception as exc:
        message = str(exc)[:500] or "Scheduled run failed"
        logger.exception("Scheduled pipeline failed for subscription %s", sub.id)
        return _fail(store, sub, run.id, message)
    finally:
        current_user_id.reset(user_token)
        current_mission_id.reset(mission_token)
    runs.update_status(run.id, RunStatus.COMPLETED, result_text=instruction)
    return {"ran": True, "run_id": run.id}


async def _fire_instruction(
    sub: Subscription,
    action: dict[str, Any],
    store: SubscriptionStore,
) -> dict[str, Any]:
    instruction = schedule_instruction(action)
    thread_id = sub.conversation_id or f"schedule:{sub.id}"
    try:
        result = await run_recurring_instruction(
            user_id=sub.user_id,
            conversation_id=thread_id,
            instruction=instruction,
            mission_id=None,
        )
    except Exception as exc:
        message = str(exc)[:500] or "Scheduled run failed"
        logger.exception("Scheduled instruction failed for subscription %s", sub.id)
        return _fail(store, sub, None, message)
    if result.get("had_error"):
        message = str(result.get("error") or "Scheduled run failed")[:500]
        return _fail(store, sub, result.get("run_id"), message)
    return {"ran": True, "run_id": result.get("run_id")}


async def fire_schedule(
    sub: Subscription,
    *,
    store: SubscriptionStore | None = None,
) -> dict[str, Any]:
    subs = store or SubscriptionStore()
    if sub.status.value == "paused":
        return {"ran": False, "skipped": "paused"}
    cadence, action = normalize_schedule(sub)
    if action.get("type") == "instruction":
        result = await _fire_instruction(sub, action, subs)
    else:
        result = await _fire_pipeline(sub, action, subs)
    if result.get("ran"):
        subs.reschedule(sub.id, advance_check(cadence, sub.next_check_at))
    return result
