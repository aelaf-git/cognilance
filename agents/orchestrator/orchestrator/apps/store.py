"""SQLite storage for app integration credentials."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from orchestrator.db import ensure_db_dir
from orchestrator.missions.store import MissionStore


class AppStore:
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
                CREATE TABLE IF NOT EXISTS app_connections (
                    app_id TEXT PRIMARY KEY,
                    credentials TEXT,
                    connected_at TEXT
                )
                """
            )

    def get_credentials(self, app_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT credentials FROM app_connections WHERE app_id = ?",
                (app_id,),
            ).fetchone()
        if not row or not row["credentials"]:
            return None
        return json.loads(row["credentials"])

    def set_credentials(self, app_id: str, credentials: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO app_connections (app_id, credentials, connected_at)
                VALUES (?, ?, ?)
                ON CONFLICT(app_id) DO UPDATE SET
                    credentials = excluded.credentials,
                    connected_at = excluded.connected_at
                """,
                (app_id, json.dumps(credentials), now),
            )

    def disconnect(self, app_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM app_connections WHERE app_id = ?", (app_id,))


def init_all_stores() -> None:
    from orchestrator.conversations.store import ConversationStore
    from orchestrator.integrations.store import IntegrationStore
    from orchestrator.subscriptions.store import SubscriptionStore
    from orchestrator.users.store import UserPreferencesStore

    MissionStore().init_db()
    AppStore().init_db()
    IntegrationStore().init_db()
    ConversationStore().init_db()
    SubscriptionStore().init_db()
    UserPreferencesStore().init_db()
    from orchestrator.drafts.store import DraftStore

    DraftStore().init_db()
