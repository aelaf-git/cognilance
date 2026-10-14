"""SQLite persistence for per-user preferences."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from orchestrator.db import ensure_db_dir


class UserPreferencesStore:
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    timezone TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def get_timezone(self, user_id: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT timezone FROM user_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row or not row["timezone"]:
            return None
        return str(row["timezone"])

    def set_timezone(self, user_id: str, timezone_name: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (user_id, timezone, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    timezone = excluded.timezone,
                    updated_at = excluded.updated_at
                """,
                (user_id, timezone_name, now),
            )
