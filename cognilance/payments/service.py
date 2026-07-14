"""PaymentService — mock-USDC funding and per-hire escrow (90/10 settle)."""

from __future__ import annotations

import uuid
from typing import Any

from cognilance.payments.config import PaymentConfig
from cognilance.payments.models import (
    EscrowStatus,
    HirePayment,
    LedgerEntryType,
    cents_to_base_units,
    usd_to_base_units,
)
from cognilance.payments.store import PaymentStore

# Platform treasury wallet id in the mock ledger (mirrors on-chain treasury).
MOCK_TREASURY_WALLET_ID = "cognilance-treasury"


class PaymentError(Exception):
    """Raised when a payment operation cannot proceed."""


class PaymentService:
    """Fund user balances and lock/release per-hire escrows.

    Default backend is a local SQLite mock ledger that mirrors
    cognilance_escrow integer math (agent_cut = amount * 90 / 100,
    platform_cut = amount - agent_cut). Keep ``PAYMENTS_USE_CHAIN`` unset —
    on-chain submission is not wired yet and will raise.
    """

    def __init__(
        self,
        config: PaymentConfig | None = None,
        store: PaymentStore | None = None,
    ) -> None:
        self.config = config or PaymentConfig.from_env()
        self.store = store or PaymentStore(self.config.db_path)
        # Ensure treasury balance row exists.
        with self.store._conn() as conn:  # noqa: SLF001 — bootstrap only
            conn.execute(
                "INSERT OR IGNORE INTO balances (wallet_id, amount_base_units) VALUES (?, 0)",
                (MOCK_TREASURY_WALLET_ID,),
            )

    def _require_mock_ledger(self) -> None:
        if not self.config.use_mock_ledger:
            raise NotImplementedError(
                "On-chain payments are not wired yet; unset PAYMENTS_USE_CHAIN"
            )

    # ---- Account funding (mock USD → USDC) --------------------------------

    def ensure_user_wallet(self, user_id: str) -> str:
        return self.store.ensure_user_wallet(user_id)

    def get_balance_base_units(self, user_id: str) -> int:
        wallet_id = self.store.ensure_user_wallet(user_id)
        return self.store.get_balance(wallet_id)

    def fund_account_usd(self, user_id: str, amount_usd: int) -> dict[str, Any]:
        """Credit mock USDC at 1 USD = 1_000_000 base units. Returns new balance."""
        self._require_mock_ledger()
        if amount_usd <= 0:
            raise PaymentError("amount_usd must be positive")
        wallet_id = self.store.ensure_user_wallet(user_id)
        amount = usd_to_base_units(amount_usd)
        self.store.credit(wallet_id, amount)
        self.store.add_ledger(
            entry_type=LedgerEntryType.CREDIT.value,
            wallet_id=wallet_id,
            amount=amount,
        )
        return {
            "user_id": user_id,
            "wallet_id": wallet_id,
            "credited_base_units": amount,
            "balance_base_units": self.store.get_balance(wallet_id),
        }

    # ---- Escrow lifecycle -------------------------------------------------

    def fund_escrow(
        self,
        *,
        hire_id: str | None = None,
        agent_wallet: str,
        amount_base_units: int,
        payer_user_id: str,
        agent_id: str | None = None,
        mission_id: str | None = None,
        price_usd_cents: int | None = None,
    ) -> HirePayment:
        """Lock funds from the payer into a per-hire escrow.

        Prefer ``amount_base_units``; if ``price_usd_cents`` is provided and
        amount is 0, cents are converted.
        """
        self._require_mock_ledger()
        if price_usd_cents is not None and amount_base_units <= 0:
            amount_base_units = cents_to_base_units(price_usd_cents)
        if amount_base_units <= 0:
            raise PaymentError("escrow amount must be positive")
        if not agent_wallet:
            raise PaymentError("agent_wallet (payout_wallet) is required")

        hire_id = hire_id or f"hire-{uuid.uuid4().hex}"
        payer_wallet = self.store.ensure_user_wallet(payer_user_id)
        try:
            self.store.debit(payer_wallet, amount_base_units)
        except ValueError as exc:
            raise PaymentError(str(exc)) from exc

        task_id = self.store.next_task_id()
        tx_sig = f"mock-fund-{task_id}"

        self.store.insert_escrow(
            {
                "hire_id": hire_id,
                "mission_id": mission_id,
                "on_chain_task_id": task_id,
                "agent_id": agent_id,
                "agent_wallet": agent_wallet,
                "payer_user_id": payer_user_id,
                "payer_wallet_id": payer_wallet,
                "amount_base_units": amount_base_units,
                "status": EscrowStatus.FUNDED.value,
                "tx_signature": tx_sig,
            }
        )
        self.store.add_ledger(
            entry_type=LedgerEntryType.DEBIT.value,
            wallet_id=payer_wallet,
            amount=amount_base_units,
            task_id=task_id,
            hire_id=hire_id,
        )
        return HirePayment(
            hire_id=hire_id,
            on_chain_task_id=task_id,
            agent_id=agent_id,
            agent_wallet=agent_wallet,
            amount_base_units=amount_base_units,
            mission_id=mission_id,
            payer_user_id=payer_user_id,
            status=EscrowStatus.FUNDED,
            tx_signature=tx_sig,
        )

    def release_escrow(self, hire_id: str) -> str:
        """Release funded escrow 90/10 to agent / treasury. Returns tx signature."""
        self._require_mock_ledger()
        row = self.store.get_escrow(hire_id)
        if row is None:
            raise PaymentError(f"Unknown hire escrow: {hire_id}")
        if row["status"] != EscrowStatus.FUNDED.value:
            raise PaymentError(
                f"Escrow {hire_id} is {row['status']}, expected funded"
            )

        amount = int(row["amount_base_units"])
        agent_cut = (amount * 90) // 100
        platform_cut = amount - agent_cut

        # Credit agent wallet id = agent_wallet pubkey string as ledger id.
        agent_ledger_id = f"agent:{row['agent_wallet']}"
        self.store.credit(agent_ledger_id, agent_cut)
        self.store.credit(MOCK_TREASURY_WALLET_ID, platform_cut)
        self.store.add_ledger(
            entry_type=LedgerEntryType.CREDIT.value,
            wallet_id=agent_ledger_id,
            amount=agent_cut,
            task_id=int(row["on_chain_task_id"]),
            hire_id=hire_id,
        )
        self.store.add_ledger(
            entry_type=LedgerEntryType.CREDIT.value,
            wallet_id=MOCK_TREASURY_WALLET_ID,
            amount=platform_cut,
            task_id=int(row["on_chain_task_id"]),
            hire_id=hire_id,
        )

        tx_sig = f"mock-release-{row['on_chain_task_id']}"
        self.store.update_escrow_status(
            hire_id, EscrowStatus.RELEASED.value, tx_signature=tx_sig
        )
        return tx_sig

    def refund_escrow(self, hire_id: str) -> str:
        """Refund full escrow amount to payer. Returns tx signature."""
        self._require_mock_ledger()
        row = self.store.get_escrow(hire_id)
        if row is None:
            raise PaymentError(f"Unknown hire escrow: {hire_id}")
        if row["status"] != EscrowStatus.FUNDED.value:
            raise PaymentError(
                f"Escrow {hire_id} is {row['status']}, expected funded"
            )

        amount = int(row["amount_base_units"])
        payer_wallet = row["payer_wallet_id"]
        self.store.credit(payer_wallet, amount)
        self.store.add_ledger(
            entry_type=LedgerEntryType.CREDIT.value,
            wallet_id=payer_wallet,
            amount=amount,
            task_id=int(row["on_chain_task_id"]),
            hire_id=hire_id,
        )

        tx_sig = f"mock-refund-{row['on_chain_task_id']}"
        self.store.update_escrow_status(
            hire_id, EscrowStatus.REFUNDED.value, tx_signature=tx_sig
        )
        return tx_sig

    def get_escrow_status(self, hire_id: str) -> EscrowStatus:
        row = self.store.get_escrow(hire_id)
        if row is None:
            raise PaymentError(f"Unknown hire escrow: {hire_id}")
        return EscrowStatus(row["status"])

    def list_mission_escrows(self, mission_id: str) -> list[HirePayment]:
        return [
            HirePayment(
                hire_id=r["hire_id"],
                on_chain_task_id=int(r["on_chain_task_id"]),
                agent_id=r.get("agent_id"),
                agent_wallet=r["agent_wallet"],
                amount_base_units=int(r["amount_base_units"]),
                mission_id=r.get("mission_id"),
                payer_user_id=r.get("payer_user_id"),
                status=EscrowStatus(r["status"]),
                tx_signature=r.get("tx_signature"),
            )
            for r in self.store.list_escrows_for_mission(mission_id)
        ]

    def agent_earnings_base_units(self, payout_wallet: str) -> int:
        return self.store.get_balance(f"agent:{payout_wallet}")

    def agent_ledger(self, payout_wallet: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_ledger_for_wallet(
            f"agent:{payout_wallet}", limit=limit
        )
