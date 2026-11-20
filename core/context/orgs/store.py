"""SQLite organizations, memberships, and email invitations."""

from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

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
    source_key: str | None = None
    fingerprint: str | None = None
    payload: dict[str, Any] | None = None
    event_ids: list[str] | None = None
    dismissed_at: datetime | None = None
    priority: str = "normal"
    assignee_account_id: str | None = None
    acknowledged_at: datetime | None = None
    suggested_next_step: str | None = None
    link: dict[str, Any] | None = None


@dataclass
class PromptProposal:
    id: str
    organization_id: str
    agent_id: str
    current_text: str
    proposed_text: str
    previous_text: str
    evidence_run_ids: list[str]
    status: str
    created_at: datetime
    decided_at: datetime | None = None


@dataclass
class AuditEvent:
    id: str
    actor_account_id: str
    organization_id: str
    action: str
    target_id: str | None
    created_at: datetime


@dataclass
class OrganizationEvent:
    id: str
    organization_id: str
    type: str
    source_id: str | None
    payload: dict[str, Any]
    created_at: datetime
    idempotency_key: str


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
                    created_at TEXT NOT NULL,
                    source_key TEXT,
                    fingerprint TEXT,
                    payload TEXT,
                    event_ids TEXT,
                    dismissed_at TEXT,
                    priority TEXT,
                    assignee_account_id TEXT,
                    acknowledged_at TEXT,
                    suggested_next_step TEXT,
                    link TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_organization_alerts_org
                    ON organization_alerts(organization_id);
                CREATE TABLE IF NOT EXISTS organization_events (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    source_id TEXT,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_organization_events_org
                    ON organization_events(organization_id, created_at);
                CREATE TABLE IF NOT EXISTS prompt_proposals (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    current_text TEXT NOT NULL,
                    proposed_text TEXT NOT NULL,
                    previous_text TEXT NOT NULL DEFAULT '',
                    evidence_run_ids TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_prompt_proposals_org
                    ON prompt_proposals(organization_id, created_at);
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    actor_account_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_events_org
                    ON audit_events(organization_id, created_at);
                """
            )
            cols = {row[1] for row in conn.execute("PRAGMA table_info(organizations)")}
            if "timezone" not in cols:
                conn.execute("ALTER TABLE organizations ADD COLUMN timezone TEXT")
            alert_cols = {row[1] for row in conn.execute("PRAGMA table_info(organization_alerts)")}
            for name in (
                "source_key",
                "fingerprint",
                "payload",
                "event_ids",
                "dismissed_at",
                "priority",
                "assignee_account_id",
                "acknowledged_at",
                "suggested_next_step",
                "link",
            ):
                if name not in alert_cols:
                    conn.execute(f"ALTER TABLE organization_alerts ADD COLUMN {name} TEXT")

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
        invitation = _invitation_from_row(row)
        self.record_audit(created_by, organization_id, "membership.invited", invitation.id)
        return invitation

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
        accepted_now = False
        invitation_id = ""
        organization_id = ""
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
            invitation_id = str(row["id"])
            organization_id = str(row["organization_id"])
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO memberships (organization_id, account_id, role, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (organization_id, account_id, row["role"], now),
                )
            conn.execute(
                """
                UPDATE invitations
                SET accepted_at = ?
                WHERE id = ? AND accepted_at IS NULL
                """,
                (now, invitation_id),
            )
            saved = conn.execute(
                """
                SELECT * FROM memberships
                WHERE organization_id = ? AND account_id = ?
                """,
                (organization_id, account_id),
            ).fetchone()
            accepted_now = True
        if accepted_now:
            self.record_audit(
                account_id, organization_id, "membership.accepted", invitation_id
            )
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
                "DELETE FROM organization_events WHERE organization_id = ?",
                (organization_id,),
            )
            if _table_exists(conn, "audit_events"):
                conn.execute(
                    "DELETE FROM audit_events WHERE organization_id = ?",
                    (organization_id,),
                )
            if _table_exists(conn, "prompt_proposals"):
                conn.execute(
                    "DELETE FROM prompt_proposals WHERE organization_id = ?",
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
        actor_account_id: str | None = None,
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
        if actor_account_id:
            self.record_audit(
                actor_account_id, organization_id, "agent_setting.updated", pack.id
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

    def set_extra_instruction(
        self,
        organization_id: str,
        agent_id: str,
        extra_instruction: str | None,
        *,
        actor_account_id: str | None = None,
    ) -> None:
        """Replace one agent's extra instruction and leave its enabled flag as it is."""
        from agents.loader import get_role

        pack = get_role(agent_id)
        if pack is None or not organization_id:
            return
        instruction = str(extra_instruction or "").strip() or None
        now = datetime.now(timezone.utc).isoformat()
        self.init_db()
        with self._conn() as conn:
            existing = conn.execute(
                """
                SELECT enabled FROM organization_agent_settings
                WHERE organization_id = ? AND agent_id = ?
                """,
                (organization_id, pack.id),
            ).fetchone()
            enabled = int(existing["enabled"]) if existing else 1
            conn.execute(
                """
                INSERT INTO organization_agent_settings (
                    organization_id, agent_id, enabled, extra_instruction, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(organization_id, agent_id) DO UPDATE SET
                    extra_instruction = excluded.extra_instruction,
                    updated_at = excluded.updated_at
                """,
                (organization_id, pack.id, enabled, instruction, now),
            )
        if actor_account_id:
            self.record_audit(
                actor_account_id, organization_id, "agent_setting.updated", pack.id
            )

    def create_prompt_proposal(
        self,
        organization_id: str,
        agent_id: str,
        proposed_text: str,
        evidence_run_ids: list[str] | None = None,
    ) -> PromptProposal:
        from agents.loader import get_role

        pack = get_role(agent_id)
        proposed = str(proposed_text or "").strip()
        if pack is None or not organization_id or not proposed:
            raise ValueError("A proposal needs an organization, a known agent, and proposed text")
        current = self.extra_instructions(organization_id).get(pack.id) or pack.prompt("system")
        proposal_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        evidence = [str(item) for item in (evidence_run_ids or []) if str(item).strip()]
        self.init_db()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO prompt_proposals (
                    id, organization_id, agent_id, current_text, proposed_text,
                    previous_text, evidence_run_ids, status, created_at
                ) VALUES (?, ?, ?, ?, ?, '', ?, 'pending', ?)
                """,
                (
                    proposal_id,
                    organization_id,
                    pack.id,
                    current,
                    proposed,
                    json.dumps(evidence),
                    now,
                ),
            )
        saved = self.get_prompt_proposal(proposal_id)
        assert saved is not None
        return saved

    def get_prompt_proposal(self, proposal_id: str) -> PromptProposal | None:
        if not proposal_id:
            return None
        self.init_db()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM prompt_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
        return _proposal_from_row(row) if row else None

    def decide_prompt_proposal(
        self,
        proposal_id: str,
        *,
        approved: bool,
        actor_account_id: str | None = None,
    ) -> PromptProposal:
        proposal = self.get_prompt_proposal(proposal_id)
        if proposal is None:
            raise ValueError("Proposal not found")
        if proposal.status != "pending":
            raise ValueError("Proposal is not pending")
        now = datetime.now(timezone.utc).isoformat()
        if not approved:
            self._set_proposal_status(proposal_id, "rejected", "", now)
        else:
            previous = self.extra_instructions(proposal.organization_id).get(proposal.agent_id, "")
            self.set_extra_instruction(
                proposal.organization_id,
                proposal.agent_id,
                proposal.proposed_text,
                actor_account_id=actor_account_id,
            )
            self._set_proposal_status(proposal_id, "approved", previous, now)
        saved = self.get_prompt_proposal(proposal_id)
        assert saved is not None
        return saved

    def restore_prompt_proposal(
        self, proposal_id: str, *, actor_account_id: str | None = None
    ) -> PromptProposal:
        proposal = self.get_prompt_proposal(proposal_id)
        if proposal is None:
            raise ValueError("Proposal not found")
        if proposal.status != "approved":
            raise ValueError("Only an approved proposal can be restored")
        self.set_extra_instruction(
            proposal.organization_id,
            proposal.agent_id,
            proposal.previous_text or None,
            actor_account_id=actor_account_id,
        )
        self.record_event(
            proposal.organization_id,
            "prompt.restored",
            source_id=proposal.id,
            payload={
                "agent_id": proposal.agent_id,
                "proposal_id": proposal.id,
                "text": proposal.previous_text,
            },
            idempotency_key=f"prompt:{proposal.id}:restored",
        )
        return proposal

    def _set_proposal_status(
        self,
        proposal_id: str,
        status: str,
        previous_text: str,
        decided_at: str,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE prompt_proposals
                SET status = ?, previous_text = ?, decided_at = ?
                WHERE id = ?
                """,
                (status, previous_text, decided_at, proposal_id),
            )

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

    def open_alert(
        self,
        organization_id: str,
        summary: str,
        *,
        kind: str,
        source_key: str,
        fingerprint: str,
        payload: dict[str, Any] | None = None,
        event_ids: list[str] | None = None,
        severity: str = "warning",
        priority: str = "normal",
        assignee_account_id: str | None = None,
        suggested_next_step: str | None = None,
        link: dict[str, Any] | None = None,
    ) -> OrganizationAlert | None:
        """Open one alert for a source. A dismissal holds until the fingerprint changes."""
        if not organization_id or not source_key or not str(summary or "").strip():
            return None
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM organization_alerts
                WHERE organization_id = ? AND source_key = ?
                """,
                (organization_id, source_key),
            ).fetchall()
        for row in rows:
            existing = _alert_from_row(row)
            if existing.dismissed_at is None:
                return None
            if existing.fingerprint == fingerprint:
                return None
        alert_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        saved = str(summary).strip()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO organization_alerts (
                    id, organization_id, kind, summary, severity, created_at,
                    source_key, fingerprint, payload, event_ids,
                    priority, assignee_account_id, suggested_next_step, link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    organization_id,
                    kind,
                    saved,
                    severity,
                    now,
                    source_key,
                    fingerprint,
                    json.dumps(payload or {}),
                    json.dumps(event_ids or []),
                    _priority(priority),
                    str(assignee_account_id).strip() or None if assignee_account_id else None,
                    str(suggested_next_step).strip() or None if suggested_next_step else None,
                    json.dumps(link or {}),
                ),
            )
        opened = self._alert_by_id(alert_id)
        assert opened is not None
        return opened

    def dismiss_alert(self, alert_id: str) -> bool:
        if not alert_id:
            return False
        self.init_db()
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                """
                UPDATE organization_alerts
                SET dismissed_at = ?
                WHERE id = ? AND dismissed_at IS NULL
                """,
                (now, alert_id),
            )
            return cursor.rowcount > 0

    def acknowledge_alert(self, alert_id: str) -> bool:
        if not alert_id:
            return False
        self.init_db()
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                """
                UPDATE organization_alerts
                SET acknowledged_at = ?
                WHERE id = ? AND acknowledged_at IS NULL
                """,
                (now, alert_id),
            )
            if cursor.rowcount > 0:
                return True
            row = conn.execute(
                "SELECT id FROM organization_alerts WHERE id = ?",
                (alert_id,),
            ).fetchone()
        return row is not None

    def get_alert(self, alert_id: str) -> OrganizationAlert | None:
        if not alert_id:
            return None
        self.init_db()
        return self._alert_by_id(alert_id)

    def _alert_by_id(self, alert_id: str) -> OrganizationAlert | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM organization_alerts WHERE id = ?",
                (alert_id,),
            ).fetchone()
        return _alert_from_row(row) if row else None

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

    def list_open_alerts(self, organization_id: str) -> list[OrganizationAlert]:
        if not organization_id:
            return []
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM organization_alerts
                WHERE organization_id = ? AND dismissed_at IS NULL
                ORDER BY created_at ASC
                """,
                (organization_id,),
            ).fetchall()
        return [_alert_from_row(row) for row in rows]


    def record_event(
        self,
        organization_id: str,
        event_type: str,
        *,
        source_id: str | None = None,
        payload: dict[str, Any] | None = None,
        idempotency_key: str,
    ) -> bool:
        """Insert one event. A repeated idempotency key leaves the existing row."""
        if not organization_id or not str(event_type or "").strip() or not idempotency_key:
            return False
        self.init_db()
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO organization_events (
                    id, organization_id, type, source_id, payload, created_at, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    organization_id,
                    str(event_type).strip(),
                    source_id,
                    json.dumps(payload or {}),
                    now,
                    idempotency_key,
                ),
            )
            return cursor.rowcount > 0

    def record_audit(
        self,
        actor_account_id: str,
        organization_id: str,
        action: str,
        target_id: str | None = None,
    ) -> AuditEvent | None:
        """Insert one audit row. A missing actor, organization, or action inserts nothing."""
        actor = str(actor_account_id or "").strip()
        organization = str(organization_id or "").strip()
        name = str(action or "").strip()
        if not actor or not organization or not name:
            return None
        event_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        target = str(target_id).strip() if target_id else None
        self.init_db()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (
                    id, actor_account_id, organization_id, action, target_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, actor, organization, name, target or None, now),
            )
            row = conn.execute(
                "SELECT * FROM audit_events WHERE id = ?",
                (event_id,),
            ).fetchone()
        return _audit_from_row(row)

    def list_audit(self, organization_id: str, action: str = "") -> list[AuditEvent]:
        if not organization_id:
            return []
        name = str(action or "").strip()
        self.init_db()
        with self._conn() as conn:
            if name:
                rows = conn.execute(
                    """
                    SELECT * FROM audit_events
                    WHERE organization_id = ? AND action = ?
                    ORDER BY created_at ASC, rowid ASC
                    """,
                    (organization_id, name),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM audit_events
                    WHERE organization_id = ?
                    ORDER BY created_at ASC, rowid ASC
                    """,
                    (organization_id,),
                ).fetchall()
        return [_audit_from_row(row) for row in rows]

    def list_events(self, organization_id: str) -> list[OrganizationEvent]:
        if not organization_id:
            return []
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM organization_events
                WHERE organization_id = ?
                ORDER BY created_at ASC
                """,
                (organization_id,),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def list_all_events(self) -> list[OrganizationEvent]:
        self.init_db()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM organization_events ORDER BY created_at ASC"
            ).fetchall()
        return [_event_from_row(row) for row in rows]


def _audit_from_row(row: sqlite3.Row) -> AuditEvent:
    target = row["target_id"]
    return AuditEvent(
        id=row["id"],
        actor_account_id=row["actor_account_id"],
        organization_id=row["organization_id"],
        action=row["action"],
        target_id=str(target) if target else None,
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _proposal_from_row(row: sqlite3.Row) -> PromptProposal:
    try:
        evidence = json.loads(row["evidence_run_ids"] or "[]")
    except (TypeError, json.JSONDecodeError):
        evidence = []
    if not isinstance(evidence, list):
        evidence = []
    decided = row["decided_at"]
    return PromptProposal(
        id=row["id"],
        organization_id=row["organization_id"],
        agent_id=row["agent_id"],
        current_text=row["current_text"],
        proposed_text=row["proposed_text"],
        previous_text=row["previous_text"] or "",
        evidence_run_ids=[str(item) for item in evidence],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        decided_at=datetime.fromisoformat(decided) if decided else None,
    )


def _event_from_row(row: sqlite3.Row) -> OrganizationEvent:
    raw = row["payload"]
    try:
        payload = json.loads(raw) if raw else {}
    except (TypeError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return OrganizationEvent(
        id=row["id"],
        organization_id=row["organization_id"],
        type=row["type"],
        source_id=row["source_id"],
        payload=payload,
        created_at=datetime.fromisoformat(row["created_at"]),
        idempotency_key=row["idempotency_key"],
    )


def _json_object(raw: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(raw) if raw else {}
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(raw: str | None) -> list[str]:
    try:
        parsed = json.loads(raw) if raw else []
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _priority(value: str | None) -> str:
    cleaned = str(value or "normal").strip().lower()
    if cleaned in {"low", "normal", "high"}:
        return cleaned
    return "normal"


def _alert_from_row(row: sqlite3.Row) -> OrganizationAlert:
    keys = row.keys()
    dismissed = row["dismissed_at"] if "dismissed_at" in keys else None
    acknowledged = row["acknowledged_at"] if "acknowledged_at" in keys else None
    return OrganizationAlert(
        id=row["id"],
        organization_id=row["organization_id"],
        kind=row["kind"],
        summary=row["summary"],
        severity=row["severity"],
        created_at=datetime.fromisoformat(row["created_at"]),
        source_key=row["source_key"] if "source_key" in keys else None,
        fingerprint=row["fingerprint"] if "fingerprint" in keys else None,
        payload=_json_object(row["payload"]) if "payload" in keys else {},
        event_ids=_json_list(row["event_ids"]) if "event_ids" in keys else [],
        dismissed_at=datetime.fromisoformat(dismissed) if dismissed else None,
        priority=_priority(row["priority"]) if "priority" in keys else "normal",
        assignee_account_id=row["assignee_account_id"] if "assignee_account_id" in keys else None,
        acknowledged_at=datetime.fromisoformat(acknowledged) if acknowledged else None,
        suggested_next_step=row["suggested_next_step"] if "suggested_next_step" in keys else None,
        link=_json_object(row["link"]) if "link" in keys else {},
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
