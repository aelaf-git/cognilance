"""Conversation persistence for chat memory."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from orchestrator.db import ensure_db_dir

SHORT_TERM_MESSAGE_LIMIT = 20


@dataclass
class Conversation:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ConversationMessage:
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: datetime


class ConversationStore:
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
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                );
                CREATE INDEX IF NOT EXISTS idx_conv_messages_conv
                    ON conversation_messages(conversation_id);
                """
            )

    def ensure_conversation(
        self,
        conversation_id: str,
        *,
        title: str = "New conversation",
    ) -> Conversation:
        existing = self.get_conversation(conversation_id)
        if existing:
            return existing
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, title[:120], now, now),
            )
        return Conversation(
            id=conversation_id,
            title=title[:120],
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def create_conversation(self, *, title: str = "New conversation") -> Conversation:
        conversation_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, title[:120], now, now),
            )
        return Conversation(
            id=conversation_id,
            title=title[:120],
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        if not row:
            return None
        return Conversation(
            id=row["id"],
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def first_user_message(self, conversation_id: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT content FROM conversation_messages
                WHERE conversation_id = ? AND role = 'user'
                ORDER BY id ASC LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
        if not row:
            return None
        return str(row["content"])

    def display_title(self, conversation: Conversation) -> str:
        if conversation.title and conversation.title != "New conversation":
            return conversation.title
        first = self.first_user_message(conversation.id)
        if first:
            return first[:80]
        return conversation.title

    def delete_conversation(self, conversation_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    def session_stats(self, conversation_id: str) -> dict[str, int | str | None]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS session_count,
                    MAX(updated_at) AS latest_at,
                    (
                        SELECT status FROM missions
                        WHERE (conversation_id = ? OR thread_id = ?)
                          AND COALESCE(hidden, 0) = 0
                        ORDER BY created_at DESC LIMIT 1
                    ) AS latest_status
                FROM missions
                WHERE (conversation_id = ? OR thread_id = ?)
                  AND COALESCE(hidden, 0) = 0
                """,
                (
                    conversation_id,
                    conversation_id,
                    conversation_id,
                    conversation_id,
                ),
            ).fetchone()
        if not row:
            return {"session_count": 0, "latest_status": None}
        return {
            "session_count": int(row["session_count"] or 0),
            "latest_status": row["latest_status"],
        }

    def list_conversations(self, *, limit: int = 30) -> list[Conversation]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            Conversation(
                id=row["id"],
                title=row["title"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def touch_conversation(self, conversation_id: str, *, title: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            if title:
                conn.execute(
                    """
                    UPDATE conversations
                    SET updated_at = ?, title = ?
                    WHERE id = ?
                    """,
                    (now, title[:120], conversation_id),
                )
            else:
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )

    def append_message(self, conversation_id: str, *, role: str, content: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, role, content, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

    def list_messages(
        self,
        conversation_id: str,
        *,
        limit: int = SHORT_TERM_MESSAGE_LIMIT,
    ) -> list[ConversationMessage]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        messages = [
            ConversationMessage(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=row["role"],
                content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in reversed(rows)
        ]
        return messages

    def to_langchain_messages(self, conversation_id: str) -> list:
        from langchain_core.messages import AIMessage, HumanMessage

        messages = self.list_messages(conversation_id, limit=SHORT_TERM_MESSAGE_LIMIT)
        result = []
        for msg in messages:
            if msg.role == "user":
                result.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                result.append(AIMessage(content=msg.content))
        return result
