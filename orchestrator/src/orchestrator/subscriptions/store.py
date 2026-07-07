"""SQLite persistence for integration subscriptions."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from orchestrator.db import ensure_db_dir
from orchestrator.subscriptions.models import Subscription, SubscriptionStatus


class SubscriptionStore:
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
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    integration TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    config TEXT NOT NULL DEFAULT '{}',
                    cursor TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'active',
                    next_check_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_from_mission_id TEXT,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_subscriptions_status_next
                    ON subscriptions(status, next_check_at);
                CREATE INDEX IF NOT EXISTS idx_subscriptions_conversation
                    ON subscriptions(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_subscriptions_user
                    ON subscriptions(user_id);

                CREATE TABLE IF NOT EXISTS subscription_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    subscription_id TEXT NOT NULL,
                    integration TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sub_notifications_conv
                    ON subscription_notifications(conversation_id, id);
                """
            )

    def _row_to_subscription(self, row: sqlite3.Row) -> Subscription:
        return Subscription(
            id=row["id"],
            user_id=row["user_id"],
            conversation_id=row["conversation_id"],
            integration=row["integration"],
            kind=row["kind"],
            config=json.loads(row["config"] or "{}"),
            cursor=json.loads(row["cursor"] or "{}"),
            status=SubscriptionStatus(row["status"]),
            next_check_at=datetime.fromisoformat(row["next_check_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            created_from_mission_id=row["created_from_mission_id"],
            error=row["error"],
        )

    def create_subscription(
        self,
        *,
        user_id: str,
        conversation_id: str,
        integration: str,
        kind: str,
        config: dict[str, Any] | None = None,
        cursor: dict[str, Any] | None = None,
        poll_interval_seconds: int = 90,
        created_from_mission_id: str | None = None,
    ) -> Subscription:
        sub_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        next_check = now + timedelta(seconds=poll_interval_seconds)
        now_iso = now.isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO subscriptions (
                    id, user_id, conversation_id, integration, kind,
                    config, cursor, status, next_check_at,
                    created_at, updated_at, created_from_mission_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sub_id,
                    user_id,
                    conversation_id,
                    integration,
                    kind,
                    json.dumps(config or {}),
                    json.dumps(cursor or {}),
                    SubscriptionStatus.ACTIVE.value,
                    next_check.isoformat(),
                    now_iso,
                    now_iso,
                    created_from_mission_id,
                ),
            )
        sub = self.get_subscription(sub_id)
        assert sub is not None
        return sub

    def get_subscription(self, subscription_id: str) -> Subscription | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE id = ?",
                (subscription_id,),
            ).fetchone()
        return self._row_to_subscription(row) if row else None

    def get_by_mission_id(self, mission_id: str) -> Subscription | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM subscriptions
                WHERE created_from_mission_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (mission_id,),
            ).fetchone()
        return self._row_to_subscription(row) if row else None

    def stop_by_mission_id(self, mission_id: str) -> bool:
        sub = self.get_by_mission_id(mission_id)
        if not sub or sub.status != SubscriptionStatus.ACTIVE:
            return False
        self.set_status(sub.id, SubscriptionStatus.STOPPED)
        return True

    def list_active_for_conversation(self, conversation_id: str) -> list[Subscription]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM subscriptions
                WHERE conversation_id = ? AND status = ?
                ORDER BY created_at DESC
                """,
                (conversation_id, SubscriptionStatus.ACTIVE.value),
            ).fetchall()
        return [self._row_to_subscription(row) for row in rows]

    def list_active_for_user(self, user_id: str) -> list[Subscription]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM subscriptions
                WHERE user_id = ? AND status = ?
                ORDER BY created_at DESC
                """,
                (user_id, SubscriptionStatus.ACTIVE.value),
            ).fetchall()
        return [self._row_to_subscription(row) for row in rows]

    def list_due(self, *, limit: int = 20) -> list[Subscription]:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM subscriptions
                WHERE status = ? AND next_check_at <= ?
                ORDER BY next_check_at ASC
                LIMIT ?
                """,
                (SubscriptionStatus.ACTIVE.value, now, limit),
            ).fetchall()
        return [self._row_to_subscription(row) for row in rows]

    def update_cursor(
        self,
        subscription_id: str,
        cursor: dict[str, Any],
        *,
        poll_interval_seconds: int = 90,
    ) -> None:
        now = datetime.now(timezone.utc)
        next_check = now + timedelta(seconds=poll_interval_seconds)
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE subscriptions
                SET cursor = ?, next_check_at = ?, updated_at = ?, error = NULL
                WHERE id = ?
                """,
                (
                    json.dumps(cursor),
                    next_check.isoformat(),
                    now.isoformat(),
                    subscription_id,
                ),
            )

    def set_status(
        self,
        subscription_id: str,
        status: SubscriptionStatus,
        *,
        error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE subscriptions
                SET status = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.value, error, now, subscription_id),
            )

    def stop_for_conversation(
        self,
        conversation_id: str,
        *,
        integration: str | None = None,
        kind: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        query = """
            UPDATE subscriptions
            SET status = ?, updated_at = ?
            WHERE conversation_id = ? AND status = ?
        """
        params: list[Any] = [
            SubscriptionStatus.STOPPED.value,
            now,
            conversation_id,
            SubscriptionStatus.ACTIVE.value,
        ]
        if integration:
            query += " AND integration = ?"
            params.append(integration)
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        with self._conn() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount

    def append_notification(
        self,
        conversation_id: str,
        *,
        subscription_id: str,
        integration: str,
        kind: str,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO subscription_notifications (
                    conversation_id, subscription_id, integration, kind,
                    summary, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    subscription_id,
                    integration,
                    kind,
                    summary,
                    json.dumps(payload or {}),
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def list_notifications(
        self,
        conversation_id: str,
        *,
        after_id: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM subscription_notifications
                WHERE conversation_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (conversation_id, after_id, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "conversation_id": row["conversation_id"],
                "subscription_id": row["subscription_id"],
                "integration": row["integration"],
                "kind": row["kind"],
                "summary": row["summary"],
                "payload": json.loads(row["payload"] or "{}"),
                "created_at": row["created_at"],
                "event": "notification",
            }
            for row in rows
        ]
