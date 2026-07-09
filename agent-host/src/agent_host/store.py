"""SQLite persistence for hosted agents."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from agent_host.config import get_settings
from agent_host.crypto import decrypt_secret, encrypt_secret


@dataclass
class HostedAgent:
    id: str
    name: str
    entry_file: str
    extract_dir: str
    status: str
    port: int | None
    pid: int | None
    error_message: str | None
    created_at: str
    updated_at: str
    env_keys: list[str] | None = None


class AgentStore:
    def __init__(self, db_path: Path | None = None) -> None:
        settings = get_settings()
        self._path = db_path or settings.db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

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
                CREATE TABLE IF NOT EXISTS hosted_agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    entry_file TEXT NOT NULL,
                    extract_dir TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'uploaded',
                    port INTEGER,
                    pid INTEGER,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_hosted_agents_status
                    ON hosted_agents(status);
                CREATE TABLE IF NOT EXISTS hosted_agent_env (
                    agent_id TEXT NOT NULL,
                    env_key TEXT NOT NULL,
                    encrypted_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (agent_id, env_key),
                    FOREIGN KEY (agent_id) REFERENCES hosted_agents(id) ON DELETE CASCADE
                );
                """
            )

    def create(
        self,
        *,
        name: str,
        entry_file: str,
        extract_dir: str,
        agent_id: str | None = None,
    ) -> HostedAgent:
        now = datetime.now(timezone.utc).isoformat()
        aid = agent_id or str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO hosted_agents (
                    id, name, entry_file, extract_dir, status,
                    port, pid, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'uploaded', NULL, NULL, NULL, ?, ?)
                """,
                (aid, name, entry_file, extract_dir, now, now),
            )
        return self.get(aid)  # type: ignore[return-value]

    def list_all(self) -> list[HostedAgent]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM hosted_agents ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_agent(row) for row in rows]

    def get(self, agent_id: str) -> HostedAgent | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM hosted_agents WHERE id = ?", (agent_id,)
            ).fetchone()
        return self._row_to_agent(row) if row else None

    def update_status(
        self,
        agent_id: str,
        *,
        status: str,
        port: int | None = None,
        pid: int | None = None,
        error_message: str | None = None,
        clear_runtime: bool = False,
    ) -> HostedAgent | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            if clear_runtime:
                conn.execute(
                    """
                    UPDATE hosted_agents
                    SET status = ?, port = NULL, pid = NULL,
                        error_message = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, error_message, now, agent_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE hosted_agents
                    SET status = ?, port = ?, pid = ?, error_message = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, port, pid, error_message, now, agent_id),
                )
        return self.get(agent_id)

    def delete(self, agent_id: str) -> bool:
        with self._conn() as conn:
            conn.execute("DELETE FROM hosted_agent_env WHERE agent_id = ?", (agent_id,))
            cur = conn.execute("DELETE FROM hosted_agents WHERE id = ?", (agent_id,))
        return cur.rowcount > 0

    def set_env_vars(self, agent_id: str, env: dict[str, str], *, merge: bool = False) -> list[str]:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            if merge:
                for key, value in sorted(env.items()):
                    conn.execute(
                        """
                        INSERT INTO hosted_agent_env (agent_id, env_key, encrypted_value, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(agent_id, env_key) DO UPDATE SET
                            encrypted_value = excluded.encrypted_value,
                            updated_at = excluded.updated_at
                        """,
                        (agent_id, key, encrypt_secret(value), now),
                    )
            else:
                conn.execute("DELETE FROM hosted_agent_env WHERE agent_id = ?", (agent_id,))
                for key, value in sorted(env.items()):
                    conn.execute(
                        """
                        INSERT INTO hosted_agent_env (agent_id, env_key, encrypted_value, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (agent_id, key, encrypt_secret(value), now),
                    )
        return self.list_env_keys(agent_id)

    def merge_env_vars(self, agent_id: str, updates: dict[str, str], *, remove_keys: list[str]) -> list[str]:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            for key in remove_keys:
                conn.execute(
                    "DELETE FROM hosted_agent_env WHERE agent_id = ? AND env_key = ?",
                    (agent_id, key),
                )
            for key, value in sorted(updates.items()):
                conn.execute(
                    """
                    INSERT INTO hosted_agent_env (agent_id, env_key, encrypted_value, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(agent_id, env_key) DO UPDATE SET
                        encrypted_value = excluded.encrypted_value,
                        updated_at = excluded.updated_at
                    """,
                    (agent_id, key, encrypt_secret(value), now),
                )
        return self.list_env_keys(agent_id)

    def list_env_keys(self, agent_id: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT env_key FROM hosted_agent_env WHERE agent_id = ? ORDER BY env_key",
                (agent_id,),
            ).fetchall()
        return [row["env_key"] for row in rows]

    def get_env_vars(self, agent_id: str) -> dict[str, str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT env_key, encrypted_value FROM hosted_agent_env WHERE agent_id = ?",
                (agent_id,),
            ).fetchall()
        return {row["env_key"]: decrypt_secret(row["encrypted_value"]) for row in rows}

    def allocated_ports(self) -> set[int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT port FROM hosted_agents WHERE port IS NOT NULL"
            ).fetchall()
        return {int(row["port"]) for row in rows}

    @staticmethod
    def _row_to_agent(row: sqlite3.Row, *, env_keys: list[str] | None = None) -> HostedAgent:
        return HostedAgent(
            id=row["id"],
            name=row["name"],
            entry_file=row["entry_file"],
            extract_dir=row["extract_dir"],
            status=row["status"],
            port=row["port"],
            pid=row["pid"],
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            env_keys=env_keys if env_keys is not None else [],
        )

    def get_with_env_keys(self, agent_id: str) -> HostedAgent | None:
        agent = self.get(agent_id)
        if agent is None:
            return None
        agent.env_keys = self.list_env_keys(agent_id)
        return agent

    def list_all_with_env_keys(self) -> list[HostedAgent]:
        agents = self.list_all()
        for agent in agents:
            agent.env_keys = self.list_env_keys(agent.id)
        return agents
