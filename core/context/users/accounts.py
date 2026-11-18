"""SQLite persistence for coordinator accounts."""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from core.context.db import ensure_db_dir

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_LEN = 16


@dataclass
class Account:
    id: str
    email: str
    display_name: str
    created_at: datetime
    updated_at: datetime


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_LEN)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return (
        f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}$"
        f"{salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n_s, r_s, p_s, salt_hex, digest_hex = encoded.split("$", 5)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    try:
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(bytes.fromhex(digest_hex)),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


class AccountStore:
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
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_accounts_email ON accounts(email);
                """
            )

    def _row_to_account(self, row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def create(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> Account:
        normalized = normalize_email(email)
        if not normalized or "@" not in normalized:
            raise ValueError("A valid email is required")
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        name = (display_name or "").strip() or normalized.split("@", 1)[0]
        account_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO accounts (
                        id, email, password_hash, display_name, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_id,
                        normalized,
                        hash_password(password),
                        name[:120],
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("An account with that email already exists") from exc
        account = self.get_by_id(account_id)
        assert account is not None
        from core.context.orgs.store import OrgStore

        OrgStore(self._path).provision_personal(account)
        return account

    def get_by_id(self, account_id: str) -> Account | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
        return self._row_to_account(row) if row else None

    def get_by_email(self, email: str) -> Account | None:
        normalized = normalize_email(email)
        if not normalized:
            return None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE email = ?",
                (normalized,),
            ).fetchone()
        return self._row_to_account(row) if row else None

    def authenticate(self, email: str, password: str) -> Account | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM accounts WHERE email = ?",
                (normalize_email(email),),
            ).fetchone()
        if not row:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return self._row_to_account(row)

    def update_profile(
        self,
        account_id: str,
        *,
        display_name: str | None = None,
    ) -> Account | None:
        account = self.get_by_id(account_id)
        if not account:
            return None
        name = account.display_name
        if display_name is not None:
            cleaned = display_name.strip()
            if cleaned:
                name = cleaned[:120]
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE accounts
                SET display_name = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, now, account_id),
            )
        return self.get_by_id(account_id)

    def change_password(
        self,
        account_id: str,
        *,
        current_password: str,
        new_password: str,
    ) -> Account:
        if not new_password or len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT password_hash FROM accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
        if not row:
            raise ValueError("Authentication required")
        if not verify_password(current_password, row["password_hash"]):
            raise ValueError("Current password is incorrect")
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE accounts
                SET password_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (hash_password(new_password), now, account_id),
            )
        account = self.get_by_id(account_id)
        assert account is not None
        return account

    def to_dict(self, account: Account, *, timezone_name: str | None = None) -> dict:
        payload = {
            "id": account.id,
            "email": account.email,
            "display_name": account.display_name,
            "created_at": account.created_at.isoformat(),
            "updated_at": account.updated_at.isoformat(),
        }
        if timezone_name is not None:
            payload["timezone"] = timezone_name
        return payload
