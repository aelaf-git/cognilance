"""SQLite store for mock balances, escrow links, and ledger mirror."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class PaymentStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or Path.home() / ".cognilance" / "payments.db"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.init_db()

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
                CREATE TABLE IF NOT EXISTS user_wallets (
                    user_id TEXT PRIMARY KEY,
                    wallet_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS balances (
                    wallet_id TEXT PRIMARY KEY,
                    amount_base_units INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS user_solana_wallets (
                    user_id TEXT PRIMARY KEY,
                    address TEXT NOT NULL,
                    provider TEXT,
                    cluster TEXT NOT NULL DEFAULT 'devnet',
                    linked_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wallet_bridges (
                    user_id TEXT NOT NULL,
                    address TEXT NOT NULL,
                    bridged_base_units INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, address)
                );
                CREATE TABLE IF NOT EXISTS task_id_seq (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    next_val INTEGER NOT NULL DEFAULT 1
                );
                INSERT OR IGNORE INTO task_id_seq (id, next_val) VALUES (1, 1);
                CREATE TABLE IF NOT EXISTS escrow_links (
                    hire_id TEXT PRIMARY KEY,
                    mission_id TEXT,
                    on_chain_task_id INTEGER NOT NULL UNIQUE,
                    agent_id TEXT,
                    agent_wallet TEXT NOT NULL,
                    payer_user_id TEXT,
                    payer_wallet_id TEXT NOT NULL,
                    amount_base_units INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    tx_signature TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_escrow_mission
                    ON escrow_links(mission_id);
                CREATE TABLE IF NOT EXISTS ledger_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    hire_id TEXT,
                    entry_type TEXT NOT NULL,
                    wallet_id TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ledger_wallet
                    ON ledger_entries(wallet_id);
                """
            )

    def ensure_user_wallet(self, user_id: str) -> str:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT wallet_id FROM user_wallets WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row:
                return str(row["wallet_id"])
            wallet_id = f"wallet-{uuid.uuid4().hex[:16]}"
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO user_wallets (user_id, wallet_id, created_at) VALUES (?, ?, ?)",
                (user_id, wallet_id, now),
            )
            conn.execute(
                "INSERT INTO balances (wallet_id, amount_base_units) VALUES (?, 0)",
                (wallet_id,),
            )
            return wallet_id

    def link_solana_wallet(
        self,
        user_id: str,
        address: str,
        *,
        provider: str | None = None,
        cluster: str = "devnet",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO user_solana_wallets (user_id, address, provider, cluster, linked_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  address = excluded.address,
                  provider = excluded.provider,
                  cluster = excluded.cluster,
                  linked_at = excluded.linked_at
                """,
                (user_id, address, provider, cluster, now),
            )

    def unlink_solana_wallet(self, user_id: str) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "DELETE FROM user_solana_wallets WHERE user_id = ?", (user_id,)
            )

    def get_solana_wallet(self, user_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM user_solana_wallets WHERE user_id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_balance(self, wallet_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT amount_base_units FROM balances WHERE wallet_id = ?",
                (wallet_id,),
            ).fetchone()
            return int(row["amount_base_units"]) if row else 0

    def credit(self, wallet_id: str, amount: int) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO balances (wallet_id, amount_base_units) VALUES (?, ?)
                ON CONFLICT(wallet_id) DO UPDATE SET
                  amount_base_units = amount_base_units + excluded.amount_base_units
                """,
                (wallet_id, amount),
            )

    def debit(self, wallet_id: str, amount: int) -> None:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT amount_base_units FROM balances WHERE wallet_id = ?",
                (wallet_id,),
            ).fetchone()
            bal = int(row["amount_base_units"]) if row else 0
            if bal < amount:
                raise ValueError(
                    f"Insufficient balance: have {bal} need {amount} (base units)"
                )
            conn.execute(
                "UPDATE balances SET amount_base_units = amount_base_units - ? WHERE wallet_id = ?",
                (amount, wallet_id),
            )

    def next_task_id(self) -> int:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT next_val FROM task_id_seq WHERE id = 1"
            ).fetchone()
            val = int(row["next_val"])
            conn.execute(
                "UPDATE task_id_seq SET next_val = next_val + 1 WHERE id = 1"
            )
            return val

    def insert_escrow(self, data: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO escrow_links (
                  hire_id, mission_id, on_chain_task_id, agent_id, agent_wallet,
                  payer_user_id, payer_wallet_id, amount_base_units, status,
                  tx_signature, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["hire_id"],
                    data.get("mission_id"),
                    data["on_chain_task_id"],
                    data.get("agent_id"),
                    data["agent_wallet"],
                    data.get("payer_user_id"),
                    data["payer_wallet_id"],
                    data["amount_base_units"],
                    data["status"],
                    data.get("tx_signature"),
                    now,
                    now,
                ),
            )

    def get_escrow(self, hire_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM escrow_links WHERE hire_id = ?", (hire_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_escrows_for_agent_wallet(self, agent_wallet: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM escrow_links WHERE agent_wallet = ? ORDER BY created_at",
                (agent_wallet,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_bridged_base_units(self, user_id: str, address: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT bridged_base_units FROM wallet_bridges WHERE user_id = ? AND address = ?",
                (user_id, address),
            ).fetchone()
            return int(row["bridged_base_units"]) if row else 0

    def set_bridged_base_units(
        self, user_id: str, address: str, amount: int
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO wallet_bridges (user_id, address, bridged_base_units, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, address) DO UPDATE SET
                  bridged_base_units = excluded.bridged_base_units,
                  updated_at = excluded.updated_at
                """,
                (user_id, address, amount, now),
            )

    def list_escrows_for_mission(self, mission_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM escrow_links WHERE mission_id = ? ORDER BY created_at",
                (mission_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_escrow_status(
        self, hire_id: str, status: str, tx_signature: str | None = None
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                UPDATE escrow_links
                SET status = ?, tx_signature = COALESCE(?, tx_signature), updated_at = ?
                WHERE hire_id = ?
                """,
                (status, tx_signature, now, hire_id),
            )

    def add_ledger(
        self,
        *,
        entry_type: str,
        wallet_id: str,
        amount: int,
        task_id: int | None = None,
        hire_id: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO ledger_entries
                  (task_id, hire_id, entry_type, wallet_id, amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, hire_id, entry_type, wallet_id, amount, now),
            )

    def list_ledger_for_wallet(
        self, wallet_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ledger_entries
                WHERE wallet_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (wallet_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
