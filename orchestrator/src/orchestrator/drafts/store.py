"""SQLite persistence for pending email/document drafts."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from orchestrator.db import ensure_db_dir

_STATUS_PENDING = "pending"
_STATUS_SENT = "sent"
_STATUS_CANCELLED = "cancelled"


class DraftStore:
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
                CREATE TABLE IF NOT EXISTS pending_drafts (
                    conversation_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (conversation_id, kind)
                )
                """
            )

    def get_pending(self, conversation_id: str, kind: str = "email") -> dict[str, Any] | None:
        if not conversation_id:
            return None
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT payload, status FROM pending_drafts
                WHERE conversation_id = ? AND kind = ? AND status = ?
                """,
                (conversation_id, kind, _STATUS_PENDING),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            return None

    def get_pending_email(self, conversation_id: str) -> dict[str, Any] | None:
        return self.get_pending(conversation_id, "email")

    def save_draft(
        self,
        conversation_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> None:
        if not conversation_id:
            raise RuntimeError("conversation_id is required to save a draft")
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO pending_drafts (conversation_id, kind, payload, status, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(conversation_id, kind) DO UPDATE SET
                    payload = excluded.payload,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (conversation_id, kind, json.dumps(payload), _STATUS_PENDING, now),
            )

    def save_email_draft(self, conversation_id: str, payload: dict[str, Any]) -> None:
        self.save_draft(conversation_id, "email", payload)

    def get_proposal_draft(self, conversation_id: str) -> dict[str, Any] | None:
        return self.get_pending(conversation_id, "proposal")

    def save_proposal_draft(self, conversation_id: str, payload: dict[str, Any]) -> None:
        self.save_draft(conversation_id, "proposal", payload)

    def get_document_draft(self, conversation_id: str) -> dict[str, Any] | None:
        return self.get_pending(conversation_id, "document")

    def save_document_draft(self, conversation_id: str, payload: dict[str, Any]) -> None:
        self.save_draft(conversation_id, "document", payload)

    def has_proposal_draft(self, conversation_id: str) -> bool:
        draft = self.get_proposal_draft(conversation_id)
        return bool(draft and draft.get("document_id"))

    def get_active_doc(self, conversation_id: str) -> dict[str, Any] | None:
        """Return the newest proposal or created Doc for this conversation."""
        if not conversation_id:
            return None
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM pending_drafts
                WHERE conversation_id = ? AND kind IN ('proposal', 'document') AND status = ?
                ORDER BY updated_at DESC
                """,
                (conversation_id, _STATUS_PENDING),
            ).fetchall()
        for row in rows:
            try:
                draft = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(draft, dict):
                continue
            document_id = str(draft.get("document_id") or "").strip()
            if not document_id:
                continue
            url = str(draft.get("url") or "").strip()
            if not url:
                url = f"https://docs.google.com/document/d/{document_id}/edit"
            return {
                "document_id": document_id,
                "url": url,
                "title": str(draft.get("title") or draft.get("name") or "Google Doc"),
            }
        return None

    def mark_sent(self, conversation_id: str, kind: str = "email") -> None:
        if not conversation_id:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE pending_drafts SET status = ?, updated_at = ?
                WHERE conversation_id = ? AND kind = ?
                """,
                (_STATUS_SENT, now, conversation_id, kind),
            )

    def has_pending_email(self, conversation_id: str) -> bool:
        return self.get_pending_email(conversation_id) is not None

    def draft_context_for_planner(self, conversation_id: str) -> str:
        draft = self.get_pending_email(conversation_id)
        if not draft:
            return ""
        subject = str(draft.get("subject") or "(no subject)")
        body = str(draft.get("body") or "")
        to_addr = str(draft.get("to") or "").strip()
        preview = body[:400] + ("…" if len(body) > 400 else "")
        lines = [
            "Pending email draft awaiting user approval:",
            f"  Subject: {subject}",
        ]
        if to_addr:
            lines.append(f"  To: {to_addr}")
        lines.append(f"  Body preview: {preview}")
        lines.append(
            "  If the user approves or provides a recipient, use send_email — do NOT compose a new draft."
        )
        return "\n".join(lines)
