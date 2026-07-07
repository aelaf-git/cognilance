"""SQLite persistence for OAuth integration tokens."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from orchestrator.db import ensure_db_dir
from orchestrator.integrations.crypto import decrypt_token, encrypt_token


@dataclass
class StoredIntegration:
    user_id: str
    integration: str
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    connected_at: datetime


class IntegrationStore:
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
                CREATE TABLE IF NOT EXISTS integrations (
                    user_id TEXT NOT NULL,
                    integration TEXT NOT NULL,
                    access_token_enc TEXT NOT NULL,
                    refresh_token_enc TEXT,
                    expires_at TEXT,
                    connected_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, integration)
                );
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    integration TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_integrations_user
                    ON integrations(user_id);
                """
            )

    def save_tokens(
        self,
        *,
        user_id: str,
        integration: str,
        access_token: str,
        refresh_token: str | None,
        expires_at: datetime | None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO integrations (
                    user_id, integration, access_token_enc, refresh_token_enc,
                    expires_at, connected_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, integration) DO UPDATE SET
                    access_token_enc = excluded.access_token_enc,
                    refresh_token_enc = excluded.refresh_token_enc,
                    expires_at = excluded.expires_at,
                    connected_at = excluded.connected_at
                """,
                (
                    user_id,
                    integration,
                    encrypt_token(access_token),
                    encrypt_token(refresh_token) if refresh_token else None,
                    expires_at.isoformat() if expires_at else None,
                    now,
                ),
            )

    def get_tokens(self, user_id: str, integration: str) -> StoredIntegration | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM integrations
                WHERE user_id = ? AND integration = ?
                """,
                (user_id, integration),
            ).fetchone()
        if not row:
            return None
        return StoredIntegration(
            user_id=row["user_id"],
            integration=row["integration"],
            access_token=decrypt_token(row["access_token_enc"]),
            refresh_token=decrypt_token(row["refresh_token_enc"])
            if row["refresh_token_enc"]
            else None,
            expires_at=datetime.fromisoformat(row["expires_at"])
            if row["expires_at"]
            else None,
            connected_at=datetime.fromisoformat(row["connected_at"]),
        )

    def is_connected(self, user_id: str, integration: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM integrations WHERE user_id = ? AND integration = ?",
                (user_id, integration),
            ).fetchone()
        return row is not None

    def list_connected(self, user_id: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT integration FROM integrations WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return [row["integration"] for row in rows]

    def disconnect(self, user_id: str, integration: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM integrations WHERE user_id = ? AND integration = ?",
                (user_id, integration),
            )

    def save_oauth_state(self, state: str, user_id: str, integration: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO oauth_states (state, user_id, integration, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (state, user_id, integration, now),
            )

    def pop_oauth_state(self, state: str) -> tuple[str, str] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT user_id, integration FROM oauth_states WHERE state = ?",
                (state,),
            ).fetchone()
            if not row:
                return None
            conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        return row["user_id"], row["integration"]
