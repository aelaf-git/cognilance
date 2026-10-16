#!/usr/bin/env python3
"""End-to-end smoke: durable Run + board graph (no registry / A2A workers)."""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def run_graph(prompt: str, *, thread_id: str | None = None) -> dict:
    from core.runtime.board.store import BoardStore
    from core.runtime.runs.models import RunTrigger
    from core.runtime.runs.store import RunStore
    from pipelines.coordinator_board.graph import ensure_graph

    rid = thread_id or str(uuid.uuid4())
    runs = RunStore()
    runs.init_db()
    BoardStore().init_db()
    runs.create_run(
        instruction=prompt,
        thread_id=rid,
        trigger=RunTrigger.MESSAGE,
        conversation_id=rid,
        run_id=rid,
    )

    graph = await ensure_graph(with_checkpointer=True)
    config = {"configurable": {"thread_id": rid}}
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=prompt)], "run_id": rid},
        config=config,
    )
    result["_run_id"] = rid
    return result


def _ui_names(result: dict) -> list[str]:
    return [
        item["name"]
        for item in (result.get("ui") or [])
        if item.get("type") == "ui"
    ]


async def main() -> None:
    from agents.loader import SPECIALISTS
    from core.runtime.board.store import BoardStore
    from core.runtime.runs.store import RunStore
    from workers.schedulers.watcher_events import enqueue_watcher_inbox_alert
    from core.broker.policy import RiskGrade, risk_for

    print("0) Registry validation...")
    from core.registry import validate_all

    report = validate_all(strict=True, log=False)
    print(f"   {report.summary()}")

    print("1) In-process roles...")
    ids = sorted(r.id for r in SPECIALISTS)
    assert ids == [
        "concept_note_writer",
        "email_agent",
        "report_writer",
        "researcher",
        "watcher",
    ], ids
    print(f"   {ids}")

    print("2) Risk policy...")
    assert risk_for("gmail.send") == RiskGrade.IRREVERSIBLE
    assert risk_for("web.search") == RiskGrade.READ
    assert risk_for("docs.create") == risk_for("google_docs.create")  # legacy alias
    print("   ok")

    print("2b) Preset pipelines...")
    from pipelines import available_pipelines
    from pipelines.weekly_report.graph import preset

    assert {"coordinator_board", "weekly_report", "concept_note", "email_followup"} <= set(
        available_pipelines()
    )
    assert [t["assignee_role"] for t in preset("x")] == ["researcher", "report_writer"]
    print(f"   {available_pipelines()}")

    print("3) Durable Run — coordinator board graph...")
    result = await run_graph(
        "What is 2+2? Answer with just the number.",
        thread_id=f"smoke-{uuid.uuid4().hex[:8]}",
    )
    rid = result["_run_id"]
    msg = result["messages"][-1]
    results = result.get("subtask_results") or []
    board_tasks = result.get("board_tasks") or []
    db_tasks = BoardStore().list_for_run(rid)
    run = RunStore().get_run(rid)
    print(f"   text: {str(msg.content)[:140]}")
    print(f"   subtask_results: {len(results)}")
    print(f"   board tasks (state/db): {len(board_tasks)}/{len(db_tasks)}")
    print(f"   run row: {run.status.value if run else 'missing'}")
    print(f"   ui: {_ui_names(result)}")
    assert run is not None, "expected durable Run row"
    assert len(db_tasks) >= 1, "expected coordinator to persist board tasks"
    assert len(results) >= 1 or str(result.get("final_text") or "").strip(), (
        "expected specialist results or final_text"
    )
    assert "text-card" not in _ui_names(result), "text-card should not be emitted"

    print("4) Watcher event enqueue...")
    event_run = enqueue_watcher_inbox_alert(
        user_id="smoke-user",
        conversation_id=f"smoke-conv-{uuid.uuid4().hex[:6]}",
        emails=[{"id": "m1", "from": "Ada <ada@example.com>", "subject": "Hello"}],
        summary='Heads up — Ada just emailed you about "Hello".',
    )
    assert event_run, "expected watcher event run id"
    event = RunStore().get_run(event_run)
    assert event is not None and event.trigger.value == "event"
    tasks = BoardStore().list_for_run(event_run)
    assert any(t.assignee_role == "watcher" for t in tasks)
    print(f"   event run {event_run} with {len(tasks)} board task(s)")

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
