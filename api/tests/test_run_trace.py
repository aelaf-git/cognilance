"""A run read shows the trace, and health reports the stores and recent failures."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.routes import health, runs
from core.context.projects.store import ProjectStore
from core.context.subscriptions.store import SubscriptionStore
from core.runtime.board.store import BoardStore
from core.runtime.runs.models import RunStatus
from core.runtime.runs.store import RunStore
from workers.schedulers.ticker import last_success_at, tick_subscriptions

FINAL = "The brief is ready."


def _app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def identify(request: Request, call_next):
        request.state.user_id = request.headers.get("x-user-id") or ""
        return await call_next(request)

    app.include_router(runs.router)
    app.include_router(health.router)
    return app


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    run_store = RunStore(db)
    board = BoardStore(db)
    for store in (run_store, board, ProjectStore(db), SubscriptionStore(db)):
        store.init_db()
    monkeypatch.setattr(runs, "run_store", run_store)
    monkeypatch.setattr(runs, "board_store", board)
    return {"db": db, "runs": run_store, "board": board, "client": TestClient(_app())}


def _stamp(db: str, table: str, row_id: str, when: datetime) -> None:
    with sqlite3.connect(db) as conn:
        conn.execute(
            f"UPDATE {table} SET created_at = ? WHERE id = ?",
            (when.isoformat(), row_id),
        )


def test_one_response_shows_the_trace_and_a_failed_specialist(world):
    runs_store: RunStore = world["runs"]
    board: BoardStore = world["board"]
    run = runs_store.create_run(
        instruction="Draft the brief",
        thread_id="thread-a",
        user_id="ada",
        run_id="run-a",
    )
    base = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    _stamp(world["db"], "runs", run.id, base)
    plan = runs_store.append_step(
        run.id, kind="task_created", text="Write the brief", data={"title": "Write the brief"}
    )
    tool = runs_store.append_step(
        run.id,
        kind="tool_call",
        text="projects.search_tasks",
        data={"tool": "projects.search_tasks", "risk": "read", "outcome": "completed"},
    )
    claimed = runs_store.append_step(
        run.id,
        kind="task_claimed",
        text="Write the brief",
        data={"task_id": "task-1", "role": "project_agent"},
    )
    approval = runs_store.append_step(
        run.id,
        kind="approval",
        text="Approval required for gmail.send",
        data={"tool": "gmail.send"},
    )
    assemble = runs_store.append_step(run.id, kind="assemble", text=FINAL, data={"result_count": 1})
    for step, seconds in (
        (plan, 1),
        (tool, 1.5),
        (claimed, 2),
        (approval, 3),
        (assemble, 4),
    ):
        _stamp(world["db"], "run_steps", step.id, base + timedelta(seconds=seconds))
    runs_store.update_status(run.id, RunStatus.COMPLETED, result_text=FINAL)
    task = board.create_task(
        run_id=run.id,
        title="Write the brief",
        instruction="Write it",
        assignee_role="project_agent",
    )
    board.complete_task(task.id, result_text="The specialist failed.", failed=True)

    response = world["client"].get(f"/runs/{run.id}", headers={"x-user-id": "ada"})
    assert response.status_code == 200, response.text
    body = response.json()
    kinds = [step["kind"] for step in body["steps"]]
    assert kinds == ["task_created", "tool_call", "task_claimed", "approval", "assemble"]
    assert body["run"]["result_text"] == FINAL
    assert body["steps"][-1]["text"] == FINAL
    assert [step["duration_ms"] for step in body["steps"]] == [1000, 500, 500, 1000, 1000]
    assert body["durations"]["specialists"] == {"project_agent": 500}
    assert body["durations"]["tools"] == {"projects.search_tasks": 500}
    assert body["board_tasks"][0]["status"] == "failed"
    assert body["board_tasks"][0]["id"] == task.id


@pytest.mark.asyncio
async def test_health_reports_the_ticker_and_fails_when_sqlite_cannot_open(world, monkeypatch):
    runs_store: RunStore = world["runs"]
    recent = runs_store.create_run(
        instruction="Recent failure",
        thread_id="thread-recent",
        user_id="ada",
        run_id="run-recent",
    )
    older = runs_store.create_run(
        instruction="Older failure",
        thread_id="thread-old",
        user_id="ada",
        run_id="run-old",
    )
    runs_store.update_status(recent.id, RunStatus.FAILED, error="boom")
    runs_store.update_status(older.id, RunStatus.FAILED, error="old")
    stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with sqlite3.connect(world["db"]) as conn:
        conn.execute("UPDATE runs SET updated_at = ? WHERE id = ?", (stale, older.id))

    await tick_subscriptions()
    response = world["client"].get("/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["sqlite"] == "ok"
    assert body["checkpointer"] == "ok"
    assert body["ticker_at"] == last_success_at()
    assert body["ticker_at"]
    assert body["failed_runs"] == 1
    assert body["failed_window_seconds"] == 3600

    blocked = Path(world["db"]).parent / "not-a-database"
    blocked.mkdir()
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", str(blocked))
    failed = world["client"].get("/health")
    assert failed.status_code == 503
    assert failed.json()["status"] == "failed"
    assert failed.json()["sqlite"] == "failed"
