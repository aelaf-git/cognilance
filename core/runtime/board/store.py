"""SQLite shared task board."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from core.runtime.board.models import BoardTask, BoardTaskStatus, SPECIALIST_ROLES
from core.context.db import ensure_db_dir


class BoardStore:
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
                CREATE TABLE IF NOT EXISTS board_tasks (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    assignee_role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    depends_on TEXT NOT NULL DEFAULT '[]',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    result_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_board_run ON board_tasks(run_id);
                CREATE INDEX IF NOT EXISTS idx_board_role_status
                    ON board_tasks(assignee_role, status);
                """
            )

    def create_task(
        self,
        *,
        run_id: str,
        title: str,
        instruction: str,
        assignee_role: str,
        depends_on: list[str] | None = None,
        task_id: str | None = None,
    ) -> BoardTask:
        from agents.loader import normalize_role_id

        role = normalize_role_id(assignee_role)
        if role not in SPECIALIST_ROLES:
            raise ValueError(f"Unknown assignee_role: {assignee_role}")
        now = datetime.now(timezone.utc)
        task = BoardTask(
            id=task_id or str(uuid.uuid4()),
            run_id=run_id,
            title=title,
            instruction=instruction,
            assignee_role=role,
            depends_on=list(depends_on or []),
            created_at=now,
            updated_at=now,
        )
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO board_tasks (
                    id, run_id, title, instruction, assignee_role, status,
                    depends_on, result_json, result_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}', '', ?, ?)
                """,
                (
                    task.id,
                    task.run_id,
                    task.title,
                    task.instruction,
                    task.assignee_role,
                    task.status.value,
                    json.dumps(task.depends_on),
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                ),
            )
        return task

    def list_for_run(self, run_id: str) -> list[BoardTask]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM board_tasks WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_task(self, task_id: str) -> BoardTask | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM board_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return self._row_to_task(row) if row else None

    def claim_open_for_role(self, run_id: str, role: str) -> list[BoardTask]:
        """Claim open tasks whose dependencies are all done."""
        from agents.loader import normalize_role_id

        role = normalize_role_id(role)
        tasks = self.list_for_run(run_id)
        done_ids = {t.id for t in tasks if t.status == BoardTaskStatus.DONE}
        claimed: list[BoardTask] = []
        for task in tasks:
            if task.assignee_role != role or task.status != BoardTaskStatus.OPEN:
                continue
            if any(dep not in done_ids for dep in task.depends_on):
                continue
            self._set_status(task.id, BoardTaskStatus.CLAIMED)
            refreshed = self.get_task(task.id)
            if refreshed:
                claimed.append(refreshed)
        return claimed

    def complete_task(
        self,
        task_id: str,
        *,
        result_text: str = "",
        result_json: dict[str, Any] | None = None,
        failed: bool = False,
    ) -> None:
        status = BoardTaskStatus.FAILED if failed else BoardTaskStatus.DONE
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE board_tasks SET
                    status = ?,
                    result_text = ?,
                    result_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    result_text,
                    json.dumps(result_json or {}),
                    now,
                    task_id,
                ),
            )

    def _set_status(self, task_id: str, status: BoardTaskStatus) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE board_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, task_id),
            )

    def _row_to_task(self, row: sqlite3.Row) -> BoardTask:
        try:
            depends = json.loads(row["depends_on"] or "[]")
        except (TypeError, json.JSONDecodeError):
            depends = []
        try:
            result = json.loads(row["result_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            result = {}
        return BoardTask(
            id=row["id"],
            run_id=row["run_id"],
            title=row["title"],
            instruction=row["instruction"],
            assignee_role=row["assignee_role"],
            status=BoardTaskStatus(row["status"]),
            depends_on=depends if isinstance(depends, list) else [],
            result_json=result if isinstance(result, dict) else {},
            result_text=row["result_text"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
