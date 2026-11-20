"""SQLite persistence for missions and SSE event logs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from core.context.db import DB_PATH, ensure_db_dir
from core.runtime.missions.models import Mission, MissionStatus
from core.runtime.missions.session_type import SessionType, detect_session_type
from core.runtime.missions.visibility import can_hide_session


class MissionStore:
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
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    instruction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_text TEXT,
                    result_ui TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS mission_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (mission_id) REFERENCES missions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
                CREATE INDEX IF NOT EXISTS idx_mission_events_mission ON mission_events(mission_id);
                """
            )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(missions)")}
            if "session_type" not in cols:
                conn.execute(
                    "ALTER TABLE missions ADD COLUMN session_type TEXT NOT NULL DEFAULT 'once'"
                )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(missions)")}
            if "hidden" not in cols:
                conn.execute(
                    "ALTER TABLE missions ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0"
                )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(missions)")}
            if "conversation_id" not in cols:
                conn.execute("ALTER TABLE missions ADD COLUMN conversation_id TEXT")
                conn.execute(
                    """
                    UPDATE missions
                    SET conversation_id = thread_id
                    WHERE conversation_id IS NULL
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_missions_conversation
                    ON missions(conversation_id)
                    """
                )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(missions)")}
            if "user_id" not in cols:
                conn.execute("ALTER TABLE missions ADD COLUMN user_id TEXT")
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_missions_user
                    ON missions(user_id)
                    """
                )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(missions)")}
            if "organization_id" not in cols:
                conn.execute("ALTER TABLE missions ADD COLUMN organization_id TEXT")
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_missions_organization
                    ON missions(organization_id)
                    """
                )

    def recover_stale_running(self, *, max_age_seconds: int = 120) -> int:
        """Mark abandoned running missions as failed (e.g. after worker crash)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id FROM missions
                WHERE status = ? AND updated_at < ?
                  AND COALESCE(session_type, 'once') = 'once'
                """,
                (MissionStatus.RUNNING.value, cutoff),
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    UPDATE missions
                    SET status = ?, error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        MissionStatus.FAILED.value,
                        "Mission interrupted or timed out",
                        now,
                        row["id"],
                    ),
                )
        return len(rows)

    def create_mission(
        self,
        *,
        instruction: str,
        thread_id: str | None = None,
        conversation_id: str | None = None,
        session_type: SessionType | None = None,
        user_id: str | None = None,
        organization_id: str | None = None,
    ) -> Mission:
        mission_id = str(uuid.uuid4())
        conversation = conversation_id or thread_id or str(uuid.uuid4())
        thread = thread_id or conversation
        kind = session_type or detect_session_type(instruction)
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO missions (
                    id, instruction, status, thread_id, conversation_id,
                    session_type, created_at, updated_at, user_id, organization_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mission_id,
                    instruction,
                    MissionStatus.QUEUED.value,
                    thread,
                    conversation,
                    kind.value,
                    now,
                    now,
                    user_id,
                    organization_id,
                ),
            )
        return Mission(
            id=mission_id,
            instruction=instruction,
            status=MissionStatus.QUEUED,
            thread_id=thread,
            conversation_id=conversation,
            session_type=kind,
            user_id=user_id,
            organization_id=organization_id,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def get_mission(
        self,
        mission_id: str,
        *,
        user_id: str | None = None,
        organization_id: str | None = None,
    ) -> Mission | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
        if not row:
            return None
        mission = self._row_to_mission(row)
        if user_id and mission.user_id and mission.user_id != user_id:
            return None
        if organization_id and mission.organization_id and mission.organization_id != organization_id:
            return None
        return mission

    def list_missions(
        self,
        *,
        limit: int = 50,
        include_hidden: bool = False,
        user_id: str | None = None,
        organization_id: str | None = None,
    ) -> list[Mission]:
        self.init_db()
        clauses: list[str] = []
        params: list[Any] = []
        if not include_hidden:
            clauses.append("COALESCE(hidden, 0) = 0")
        if organization_id:
            clauses.append("organization_id = ?")
            params.append(organization_id)
        elif user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM missions{where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_mission(row) for row in rows]

    def list_missions_for_conversation(
        self,
        conversation_id: str,
        *,
        limit: int = 50,
        include_hidden: bool = False,
        user_id: str | None = None,
        organization_id: str | None = None,
    ) -> list[Mission]:
        self.init_db()
        clauses = ["(conversation_id = ? OR thread_id = ?)"]
        params: list[Any] = [conversation_id, conversation_id]
        if not include_hidden:
            clauses.append("COALESCE(hidden, 0) = 0")
        if organization_id:
            clauses.append("organization_id = ?")
            params.append(organization_id)
        elif user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM missions
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at ASC LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._row_to_mission(row) for row in rows]

    def delete_missions_for_conversation(self, conversation_id: str) -> int:
        """Abort running missions and remove all missions/events for a conversation."""
        self.init_db()
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            running = conn.execute(
                """
                SELECT id FROM missions
                WHERE (conversation_id = ? OR thread_id = ?)
                  AND status IN (?, ?)
                """,
                (
                    conversation_id,
                    conversation_id,
                    MissionStatus.RUNNING.value,
                    MissionStatus.QUEUED.value,
                ),
            ).fetchall()
            for row in running:
                conn.execute(
                    """
                    UPDATE missions
                    SET status = ?, error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (MissionStatus.CANCELLED.value, "Conversation deleted", now, row["id"]),
                )
            mission_ids = [
                r["id"]
                for r in conn.execute(
                    """
                    SELECT id FROM missions
                    WHERE conversation_id = ? OR thread_id = ?
                    """,
                    (conversation_id, conversation_id),
                ).fetchall()
            ]
            for mission_id in mission_ids:
                conn.execute("DELETE FROM mission_events WHERE mission_id = ?", (mission_id,))
            conn.execute(
                "DELETE FROM missions WHERE conversation_id = ? OR thread_id = ?",
                (conversation_id, conversation_id),
            )
        return len(mission_ids)

    def hide_session(self, mission_id: str) -> None:
        self.init_db()
        mission = self.get_mission(mission_id)
        if not mission:
            raise KeyError("Session not found")
        if not can_hide_session(mission):
            raise ValueError("Active or unaborted sessions cannot be dismissed")
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE missions SET hidden = 1, updated_at = ? WHERE id = ?",
                (now, mission_id),
            )

    def claim_next_queued(self) -> Mission | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM missions WHERE status = ?
                ORDER BY created_at ASC LIMIT 1
                """,
                (MissionStatus.QUEUED.value,),
            ).fetchone()
            if not row:
                return None
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE missions SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
                (MissionStatus.RUNNING.value, now, row["id"], MissionStatus.QUEUED.value),
            )
            updated = conn.execute(
                "SELECT * FROM missions WHERE id = ?", (row["id"],)
            ).fetchone()
        if not updated or updated["status"] != MissionStatus.RUNNING.value:
            return None
        return self._row_to_mission(updated)

    def update_session_type(self, mission_id: str, session_type: SessionType) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE missions SET session_type = ?, updated_at = ? WHERE id = ?",
                (session_type.value, now, mission_id),
            )

    def update_status(
        self,
        mission_id: str,
        status: MissionStatus,
        *,
        result_text: str | None = None,
        result_ui: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE missions
                SET status = ?, updated_at = ?, result_text = COALESCE(?, result_text),
                    result_ui = COALESCE(?, result_ui), error = COALESCE(?, error)
                WHERE id = ?
                """,
                (
                    status.value,
                    now,
                    result_text,
                    json.dumps(result_ui) if result_ui is not None else None,
                    error,
                    mission_id,
                ),
            )

    def append_event(self, mission_id: str, payload: dict[str, Any]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO mission_events (mission_id, payload, created_at)
                VALUES (?, ?, ?)
                """,
                (mission_id, json.dumps(payload), now),
            )
            return int(cursor.lastrowid)

    def list_events(self, mission_id: str, *, after_id: int = 0) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, payload FROM mission_events
                WHERE mission_id = ? AND id > ?
                ORDER BY id ASC
                """,
                (mission_id, after_id),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload"])
            payload["_event_id"] = row["id"]
            events.append(payload)
        return events

    def _row_to_mission(self, row: sqlite3.Row) -> Mission:
        result_ui = json.loads(row["result_ui"]) if row["result_ui"] else None
        raw_type = row["session_type"] if "session_type" in row.keys() else "once"
        raw_conversation = row["conversation_id"] if "conversation_id" in row.keys() else None
        return Mission(
            id=row["id"],
            instruction=row["instruction"],
            status=MissionStatus(row["status"]),
            thread_id=row["thread_id"],
            conversation_id=raw_conversation or row["thread_id"],
            session_type=SessionType(raw_type or "once"),
            user_id=row["user_id"] if "user_id" in row.keys() else None,
            organization_id=row["organization_id"] if "organization_id" in row.keys() else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            result_text=row["result_text"],
            result_ui=result_ui,
            error=row["error"],
        )
