"""SQLite organizations, memberships, and email invitations."""

from __future__ import annotations

import secrets
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

from core.context.db import ensure_db_dir
from core.context.users.accounts import normalize_email

_RESOURCE_TABLES = ("conversations", "runs", "missions", "subscriptions")
ROLES = ("member", "admin", "owner")
INVITE_ROLES = ("member", "admin")
ROLE_RANK = {"member": 1, "admin": 2, "owner": 3}


@dataclass
class Organization:
    id: str
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass
class Membership:
    organization_id: str
    account_id: str
    role: str
    created_at: datetime


@dataclass
class OrganizationNote:
    id: str
    organization_id: str
    body: str
    created_at: datetime


@dataclass
class OrganizationAlert:
    id: str
    organization_id: str
    kind: str
    summary: str
    severity: str
    created_at: datetime


@dataclass
class Invitation:
    id: str
    organization_id: str
    email: str
    role: str
    token: str
    created_by: str
    created_at: datetime
    accepted_at: datetime | None


class OrgStore:
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
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memberships (
                    organization_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (organization_id, account_id)
                );
                CREATE INDEX IF NOT EXISTS idx_memberships_account
                    ON memberships(account_id);
                CREATE TABLE IF NOT EXISTS invitations (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    accepted_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_invitations_email
                    ON invitations(email);
                CREATE TABLE IF NOT EXISTS organization_agent_settings (
                    organization_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    extra_instruction TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (organization_id, agent_id)
                );
                CREATE TABLE IF NOT EXISTS organization_notes (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_organization_notes_org
                    ON organization_notes(organization_id);
                CREATE TABLE IF NOT EXISTS organization_alerts (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_organization_alerts_org
                    ON organization_alerts(organization_id);
                """
            )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(organizations)")}
            if "timezone" not in cols:
                conn.execute("ALTER TABLE organizations ADD COLUMN timezone TEXT")

    def provision_personal(self, account) -> str:
        """Create one owner membership. A second call for the same account does nothing."""
        self.init_db()
        existing = self.active_for_account(account.id)
        if existing:
            return existing
        org_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        name = str(getattr(account, "display_name", "") or "").strip() or "Personal"
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO organizations (id, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (org_id, name[:120], now, now),
            )
            conn.execute(
                """
                INSERT INTO memberships (organization_id, account_id, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (org_id, account.id, "owner", now),
            )
        return org_id

    def active_for_account(self, account_id: str) -> str | None:
        if not account_id:
            return None
        with self._conn() as conn:
            if not _table_exists(conn, "memberships"):
                return None
            row = conn.execute(
                """
                SELECT organization_id FROM memberships
                WHERE account_id = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (account_id,),
            ).fetchone()
        return str(row["organization_id"]) if row else None

    def get_organization(self, organization_id: str) -> Organization | None:
        if not organization_id:
            return None
        self.init_db()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM organizations WHERE id = ?",
                (organization_id,),
            ).fetchone()
        if not row:
            return None
        return Organization(
            id=row["id"],
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_timezone(self, organization_id: str) -> str | None:
        if not organization_id:
            return None
        self.init_db()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT timezone FROM organizations WHERE id = ?",
                (organization_id,),
            ).fetchone()
        if not row or not row["timezone"]:
            return None
        return str(row["timezone"])

    def set_timezone(self, organization_id: str, timezone_name: str) -> None:
        if not organization_id or not timezone_name:
            raise ValueError("Organization not found")
        self.init_db()
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            updated = conn.execute(
                """
                UPDATE organizations
                SET timezone = ?, updated_at = ?
                WHERE id = ?
                """,
                (timezone_name, now, organization_id),
            ).rowcount
        if not updated:
            raise ValueError("Organization not found")

    def membership_for(self, account_id: str, organization_id: str) -> Membership | None:
        if not account_id or not organization_id:
            return None
        self.init_db()
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM memberships
                WHERE account_id = ? AND organization_id = ?
                """,
                (account_id, organization_id),
            ).fetchone()
        return _membership_from_row(row) if row else None

    def memberships_for(self, account_id: str) -> list[Membership]:
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memberships
                WHERE account_id = ?
                ORDER BY created_at ASC
                """,
                (account_id,),
            ).fetchall()
        return [_membership_from_row(row) for row in rows]

    def add_membership(self, organization_id: str, account_id: str, role: str) -> Membership:
        cleaned = str(role or "").strip().lower()
        if cleaned not in ROLES:
            raise ValueError("Unknown role")
        existing = self.membership_for(account_id, organization_id)
        if existing:
            return existing
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memberships (organization_id, account_id, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (organization_id, account_id, cleaned, now),
            )
        saved = self.membership_for(account_id, organization_id)
        if saved is None:
            raise ValueError("Organization not found")
        return saved

    def create_invitation(
        self,
        organization_id: str,
        email: str,
        *,
        created_by: str,
        role: str = "member",
    ) -> Invitation:
        cleaned_email = normalize_email(email)
        if "@" not in cleaned_email:
            raise ValueError("A valid email is required")
        cleaned_role = str(role or "member").strip().lower()
        if cleaned_role == "owner" or cleaned_role not in INVITE_ROLES:
            raise ValueError("Invitations cannot grant the owner role")
        self.init_db()
        if self.get_organization(organization_id) is None:
            raise ValueError("Organization not found")
        with self._conn() as conn:
            pending = conn.execute(
                """
                SELECT 1 FROM invitations
                WHERE organization_id = ? AND email = ? AND accepted_at IS NULL
                """,
                (organization_id, cleaned_email),
            ).fetchone()
            if pending:
                raise ValueError("An invitation for that email is already pending")
            invitation_id = str(uuid.uuid4())
            token = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO invitations (
                    id, organization_id, email, role, token, created_by, created_at, accepted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    invitation_id,
                    organization_id,
                    cleaned_email,
                    cleaned_role,
                    token,
                    created_by,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM invitations WHERE id = ?",
                (invitation_id,),
            ).fetchone()
        return _invitation_from_row(row)

    def pending_invitations_for_email(self, email: str) -> list[Invitation]:
        cleaned = normalize_email(email)
        if not cleaned:
            return []
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM invitations
                WHERE email = ? AND accepted_at IS NULL
                ORDER BY created_at ASC
                """,
                (cleaned,),
            ).fetchall()
        return [_invitation_from_row(row) for row in rows]

    def accept_invitation(self, token: str, account) -> Membership | None:
        """Accept once. A second accept leaves the existing membership in place."""
        self.init_db()
        account_id = str(getattr(account, "id", "") or "")
        email = normalize_email(getattr(account, "email", ""))
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM invitations WHERE token = ?",
                (token,),
            ).fetchone()
            if row is None:
                raise ValueError("Invitation not found")
            if email != row["email"]:
                raise ValueError("This invitation is for a different email")
            existing = conn.execute(
                """
                SELECT * FROM memberships
                WHERE organization_id = ? AND account_id = ?
                """,
                (row["organization_id"], account_id),
            ).fetchone()
            if row["accepted_at"]:
                return _membership_from_row(existing) if existing else None
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO memberships (organization_id, account_id, role, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (row["organization_id"], account_id, row["role"], now),
                )
            conn.execute(
                """
                UPDATE invitations
                SET accepted_at = ?
                WHERE id = ? AND accepted_at IS NULL
                """,
                (now, row["id"]),
            )
            saved = conn.execute(
                """
                SELECT * FROM memberships
                WHERE organization_id = ? AND account_id = ?
                """,
                (row["organization_id"], account_id),
            ).fetchone()
        return _membership_from_row(saved) if saved else None

    def delete_organization(self, organization_id: str) -> None:
        """Remove the organization, its memberships, invitations, and agent settings."""
        self.init_db()
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM invitations WHERE organization_id = ?",
                (organization_id,),
            )
            conn.execute(
                "DELETE FROM memberships WHERE organization_id = ?",
                (organization_id,),
            )
            conn.execute(
                "DELETE FROM organization_notes WHERE organization_id = ?",
                (organization_id,),
            )
            conn.execute(
                "DELETE FROM organization_alerts WHERE organization_id = ?",
                (organization_id,),
            )
            conn.execute(
                "DELETE FROM organizations WHERE id = ?",
                (organization_id,),
            )

    def backfill(self) -> None:
        """Give every account a personal organization and stamp its existing rows."""
        self.init_db()
        with self._conn() as conn:
            if not _table_exists(conn, "accounts"):
                return
            accounts = conn.execute("SELECT id, display_name FROM accounts").fetchall()
        for row in accounts:
            org_id = self.provision_personal(
                SimpleNamespace(id=row["id"], display_name=row["display_name"])
            )
            self._stamp_resources(org_id, str(row["id"]))

    def _stamp_resources(self, organization_id: str, account_id: str) -> None:
        with self._conn() as conn:
            for table in _RESOURCE_TABLES:
                if not _table_exists(conn, table):
                    continue
                if not _has_column(conn, table, "organization_id"):
                    continue
                if not _has_column(conn, table, "user_id"):
                    continue
                conn.execute(
                    f"""
                    UPDATE {table}
                    SET organization_id = ?
                    WHERE user_id = ? AND organization_id IS NULL
                    """,
                    (organization_id, account_id),
                )

    def set_agent_setting(
        self,
        organization_id: str,
        agent_id: str,
        *,
        enabled: bool = True,
        extra_instruction: str | None = None,
    ) -> None:
        """Store one organization's agent flag. Unknown agent ids are ignored."""
        from agents.loader import get_role

        pack = get_role(agent_id)
        if pack is None or not organization_id:
            return
        instruction = str(extra_instruction or "").strip() or None
        now = datetime.now(timezone.utc).isoformat()
        self.init_db()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO organization_agent_settings (
                    organization_id, agent_id, enabled, extra_instruction, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(organization_id, agent_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    extra_instruction = excluded.extra_instruction,
                    updated_at = excluded.updated_at
                """,
                (organization_id, pack.id, 1 if enabled else 0, instruction, now),
            )

    def disabled_agent_ids(self, organization_id: str) -> set[str]:
        if not organization_id:
            return set()
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT agent_id FROM organization_agent_settings
                WHERE organization_id = ? AND enabled = 0
                """,
                (organization_id,),
            ).fetchall()
        from agents.loader import get_role

        return {str(row["agent_id"]) for row in rows if get_role(str(row["agent_id"]))}

    def extra_instructions(self, organization_id: str) -> dict[str, str]:
        if not organization_id:
            return {}
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT agent_id, extra_instruction FROM organization_agent_settings
                WHERE organization_id = ? AND extra_instruction IS NOT NULL
                """,
                (organization_id,),
            ).fetchall()
        from agents.loader import get_role

        extras: dict[str, str] = {}
        for row in rows:
            agent_id = str(row["agent_id"])
            text = str(row["extra_instruction"] or "").strip()
            if text and get_role(agent_id):
                extras[agent_id] = text
        return extras

    def add_note(self, organization_id: str, body: str) -> OrganizationNote:
        cleaned = str(body or "").strip()
        if not organization_id or not cleaned:
            raise ValueError("A note needs an organization and a body")
        note_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.init_db()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO organization_notes (id, organization_id, body, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (note_id, organization_id, cleaned, now),
            )
        return OrganizationNote(
            id=note_id,
            organization_id=organization_id,
            body=cleaned,
            created_at=datetime.fromisoformat(now),
        )

    def list_notes(self, organization_id: str, *, limit: int = 3) -> list[OrganizationNote]:
        if not organization_id:
            return []
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM organization_notes
                WHERE organization_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (organization_id, max(0, int(limit))),
            ).fetchall()
        return [_note_from_row(row) for row in rows]

    def get_note(self, note_id: str, *, organization_id: str) -> OrganizationNote | None:
        if not organization_id or not note_id:
            return None
        self.init_db()
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM organization_notes
                WHERE id = ? AND organization_id = ?
                """,
                (note_id, organization_id),
            ).fetchone()
        return _note_from_row(row) if row else None


    def add_alert(
        self,
        organization_id: str,
        summary: str,
        *,
        kind: str = "info",
        severity: str = "info",
    ) -> OrganizationAlert:
        cleaned = str(summary or "").strip()
        if not organization_id or not cleaned:
            raise ValueError("An alert needs an organization and a summary")
        alert_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        saved_kind = str(kind or "info").strip() or "info"
        saved_severity = str(severity or "info").strip().lower() or "info"
        self.init_db()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO organization_alerts (
                    id, organization_id, kind, summary, severity, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (alert_id, organization_id, saved_kind, cleaned, saved_severity, now),
            )
        return OrganizationAlert(
            id=alert_id,
            organization_id=organization_id,
            kind=saved_kind,
            summary=cleaned,
            severity=saved_severity,
            created_at=datetime.fromisoformat(now),
        )

    def list_alerts(self, organization_id: str) -> list[OrganizationAlert]:
        if not organization_id:
            return []
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM organization_alerts
                WHERE organization_id = ?
                ORDER BY created_at ASC
                """,
                (organization_id,),
            ).fetchall()
        return [_alert_from_row(row) for row in rows]


def _alert_from_row(row: sqlite3.Row) -> OrganizationAlert:
    return OrganizationAlert(
        id=row["id"],
        organization_id=row["organization_id"],
        kind=row["kind"],
        summary=row["summary"],
        severity=row["severity"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _note_from_row(row: sqlite3.Row) -> OrganizationNote:
    return OrganizationNote(
        id=row["id"],
        organization_id=row["organization_id"],
        body=row["body"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _membership_from_row(row: sqlite3.Row) -> Membership:
    return Membership(
        organization_id=row["organization_id"],
        account_id=row["account_id"],
        role=row["role"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _invitation_from_row(row: sqlite3.Row) -> Invitation:
    accepted = row["accepted_at"]
    return Invitation(
        id=row["id"],
        organization_id=row["organization_id"],
        email=row["email"],
        role=row["role"],
        token=row["token"],
        created_by=row["created_by"],
        created_at=datetime.fromisoformat(row["created_at"]),
        accepted_at=datetime.fromisoformat(accepted) if accepted else None,
    )


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)
