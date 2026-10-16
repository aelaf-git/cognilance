"""SQLite persistence for durable Runs and step logs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from core.context.db import ensure_db_dir
from core.runtime.runs.models import Run, RunStatus, RunStep, RunTrigger


class RunStore:
    def __init__(self, db_path: str | None = None) -> None:
        self._path = str(db_path or ensure_db_dir())

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    instruction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    conversation_id TEXT,
                    user_id TEXT,
                    mission_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_text TEXT,
                    result_ui TEXT,
                    error TEXT,
                    pending_approval TEXT
                );
                CREATE TABLE IF NOT EXISTS run_steps (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL DEFAULT '',
                    data TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                );
                CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
                CREATE INDEX IF NOT EXISTS idx_runs_thread ON runs(thread_id);
                CREATE INDEX IF NOT EXISTS idx_run_steps_run ON run_steps(run_id);
                """
            )

    def create_run(
        self,
        *,
        instruction: str,
        thread_id: str,
        trigger: RunTrigger = RunTrigger.MESSAGE,
        conversation_id: str | None = None,
        user_id: str | None = None,
        mission_id: str | None = None,
        run_id: str | None = None,
    ) -> Run:
        now = datetime.now(timezone.utc)
        rid = run_id or str(uuid.uuid4())
        run = Run(
            id=rid,
            instruction=instruction,
            status=RunStatus.QUEUED,
            trigger=trigger,
            thread_id=thread_id,
            conversation_id=conversation_id or thread_id,
            user_id=user_id,
            mission_id=mission_id or rid,
            created_at=now,
            updated_at=now,
        )
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    id, instruction, status, trigger, thread_id, conversation_id,
                    user_id, mission_id, created_at, updated_at, result_text,
                    result_ui, error, pending_approval
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                """,
                (
                    run.id,
                    run.instruction,
                    run.status.value,
                    run.trigger.value,
                    run.thread_id,
                    run.conversation_id,
                    run.user_id,
                    run.mission_id,
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )
        return run

    def get_run(self, run_id: str) -> Run | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def update_status(
        self,
        run_id: str,
        status: RunStatus,
        *,
        error: str | None = None,
        result_text: str | None = None,
        result_ui: list | None = None,
        pending_approval: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE runs SET
                    status = ?,
                    updated_at = ?,
                    error = COALESCE(?, error),
                    result_text = COALESCE(?, result_text),
                    result_ui = COALESCE(?, result_ui),
                    pending_approval = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    now,
                    error,
                    result_text,
                    json.dumps(result_ui) if result_ui is not None else None,
                    json.dumps(pending_approval) if pending_approval is not None else None,
                    run_id,
                ),
            )

    def append_step(
        self,
        run_id: str,
        *,
        kind: str,
        text: str = "",
        data: dict[str, Any] | None = None,
    ) -> RunStep:
        step = RunStep(
            id=str(uuid.uuid4()),
            run_id=run_id,
            kind=kind,
            text=text,
            data=data or {},
        )
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO run_steps (id, run_id, kind, text, data, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    step.id,
                    step.run_id,
                    step.kind,
                    step.text,
                    json.dumps(step.data),
                    step.created_at.isoformat(),
                ),
            )
        return step

    def list_steps(self, run_id: str) -> list[RunStep]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM run_steps WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [self._row_to_step(r) for r in rows]

    def _row_to_run(self, row: sqlite3.Row) -> Run:
        pending = None
        raw = row["pending_approval"]
        if raw:
            try:
                pending = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                pending = None
        ui = None
        if row["result_ui"]:
            try:
                ui = json.loads(row["result_ui"])
            except (TypeError, json.JSONDecodeError):
                ui = []
        return Run(
            id=row["id"],
            instruction=row["instruction"],
            status=RunStatus(row["status"]),
            trigger=RunTrigger(row["trigger"]),
            thread_id=row["thread_id"],
            conversation_id=row["conversation_id"],
            user_id=row["user_id"],
            mission_id=row["mission_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            result_text=row["result_text"],
            result_ui=ui,
            error=row["error"],
            pending_approval=pending,
        )

    def _row_to_step(self, row: sqlite3.Row) -> RunStep:
        try:
            data = json.loads(row["data"] or "{}")
        except (TypeError, json.JSONDecodeError):
            data = {}
        return RunStep(
            id=row["id"],
            run_id=row["run_id"],
            kind=row["kind"],
            text=row["text"] or "",
            data=data if isinstance(data, dict) else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )
