"""SQLite persistence for OAuth integration tokens."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterator

from core.context.db import ensure_db_dir
from core.broker.crypto import decrypt_token, encrypt_token


@dataclass
class StoredIntegration:
    user_id: str
    integration: str
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    connected_at: datetime
    organization_id: str | None = None
    selected_repos: list[str] = field(default_factory=list)


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
                    created_at TEXT NOT NULL,
                    payload TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_integrations_user
                    ON integrations(user_id);
                """
            )
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(oauth_states)").fetchall()
            }
            if "payload" not in cols:
                conn.execute("ALTER TABLE oauth_states ADD COLUMN payload TEXT")
            integration_cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(integrations)").fetchall()
            }
            if "organization_id" not in integration_cols:
                conn.execute("ALTER TABLE integrations ADD COLUMN organization_id TEXT")
            if "selected_repos" not in integration_cols:
                conn.execute(
                    "ALTER TABLE integrations ADD COLUMN selected_repos TEXT NOT NULL DEFAULT '[]'"
                )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_integrations_org
                ON integrations(organization_id, integration)
                WHERE organization_id IS NOT NULL
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
        return self._stored(row)

    def is_connected(self, user_id: str, integration: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM integrations
                WHERE user_id = ? AND integration = ? AND organization_id IS NULL
                """,
                (user_id, integration),
            ).fetchone()
        return row is not None

    def list_connected(self, user_id: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT integration FROM integrations
                WHERE user_id = ? AND organization_id IS NULL
                """,
                (user_id,),
            ).fetchall()
        return [row["integration"] for row in rows]

    def disconnect(self, user_id: str, integration: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                DELETE FROM integrations
                WHERE user_id = ? AND integration = ? AND organization_id IS NULL
                """,
                (user_id, integration),
            )

    def save_org_grant(
        self,
        *,
        organization_id: str,
        integration: str,
        access_token: str,
        refresh_token: str | None,
        expires_at: datetime | None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row_user = f"org:{organization_id}"
        enc_access = encrypt_token(access_token)
        enc_refresh = encrypt_token(refresh_token) if refresh_token else None
        expires = expires_at.isoformat() if expires_at else None
        with self._conn() as conn:
            existing = conn.execute(
                """
                SELECT user_id FROM integrations
                WHERE organization_id = ? AND integration = ?
                """,
                (organization_id, integration),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE integrations
                    SET access_token_enc = ?, refresh_token_enc = ?,
                        expires_at = ?, connected_at = ?
                    WHERE organization_id = ? AND integration = ?
                    """,
                    (enc_access, enc_refresh, expires, now, organization_id, integration),
                )
                return
            conn.execute(
                """
                INSERT INTO integrations (
                    user_id, integration, access_token_enc, refresh_token_enc,
                    expires_at, connected_at, organization_id, selected_repos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]')
                """,
                (
                    row_user,
                    integration,
                    enc_access,
                    enc_refresh,
                    expires,
                    now,
                    organization_id,
                ),
            )

    def get_org_grant(self, organization_id: str, integration: str) -> StoredIntegration | None:
        if not organization_id:
            return None
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM integrations
                WHERE organization_id = ? AND integration = ?
                """,
                (organization_id, integration),
            ).fetchone()
        if not row:
            return None
        return self._stored(row)

    def is_org_connected(self, organization_id: str, integration: str) -> bool:
        if not organization_id:
            return False
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM integrations
                WHERE organization_id = ? AND integration = ?
                """,
                (organization_id, integration),
            ).fetchone()
        return row is not None

    def disconnect_org(self, organization_id: str, integration: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                DELETE FROM integrations
                WHERE organization_id = ? AND integration = ?
                """,
                (organization_id, integration),
            )

    def set_selected_repos(
        self, organization_id: str, integration: str, repo_ids: list[str]
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE integrations
                SET selected_repos = ?
                WHERE organization_id = ? AND integration = ?
                """,
                (json.dumps(repo_ids), organization_id, integration),
            )

    def _stored(self, row) -> StoredIntegration:
        keys = row.keys()
        organization_id = row["organization_id"] if "organization_id" in keys else None
        raw_repos = row["selected_repos"] if "selected_repos" in keys else "[]"
        try:
            selected = json.loads(raw_repos or "[]")
        except json.JSONDecodeError:
            selected = []
        if not isinstance(selected, list):
            selected = []
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
            organization_id=organization_id,
            selected_repos=[str(item) for item in selected],
        )

    def save_oauth_state(
        self,
        state: str,
        user_id: str,
        integration: str,
        payload: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO oauth_states (state, user_id, integration, created_at, payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (state, user_id, integration, now, payload),
            )

    def pop_oauth_state(self, state: str) -> tuple[str, str, str | None] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT user_id, integration, payload FROM oauth_states WHERE state = ?",
                (state,),
            ).fetchone()
            if not row:
                return None
            conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        return row["user_id"], row["integration"], row["payload"]
