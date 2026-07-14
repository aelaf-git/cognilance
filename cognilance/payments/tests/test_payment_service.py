"""Unit tests for PaymentService mock ledger (no Solana required)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cognilance.payments.config import PaymentConfig
from cognilance.payments.models import EscrowStatus
from cognilance.payments.service import PaymentError, PaymentService
from cognilance.payments.store import PaymentStore


class PaymentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        db = Path(self._tmp.name) / "pay.db"
        self.svc = PaymentService(
            PaymentConfig(enabled=True, use_mock_ledger=True, db_path=db),
            store=PaymentStore(db),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_fund_account_and_escrow_release_9010(self) -> None:
        self.svc.fund_account_usd("user-a", 1)  # 1_000_000 base units
        self.assertEqual(self.svc.get_balance_base_units("user-a"), 1_000_000)

        hire = self.svc.fund_escrow(
            hire_id="hire-1",
            agent_wallet="AgentWallet111",
            amount_base_units=1_000_000,
            payer_user_id="user-a",
            mission_id="mission-1",
        )
        self.assertEqual(hire.status, EscrowStatus.FUNDED)
        self.assertEqual(self.svc.get_balance_base_units("user-a"), 0)

        self.svc.release_escrow("hire-1")
        self.assertEqual(self.svc.get_escrow_status("hire-1"), EscrowStatus.RELEASED)
        self.assertEqual(self.svc.agent_earnings_base_units("AgentWallet111"), 900_000)
        # platform gets remainder
        self.assertEqual(
            self.svc.store.get_balance("cognilance-treasury"),
            100_000,
        )

    def test_non_round_split(self) -> None:
        self.svc.fund_account_usd("u", 1)
        self.svc.fund_escrow(
            hire_id="h101",
            agent_wallet="W",
            amount_base_units=101,
            payer_user_id="u",
        )
        self.svc.release_escrow("h101")
        self.assertEqual(self.svc.agent_earnings_base_units("W"), 90)
        self.assertEqual(self.svc.store.get_balance("cognilance-treasury"), 11)

    def test_refund_path(self) -> None:
        self.svc.fund_account_usd("u", 1)
        self.svc.fund_escrow(
            hire_id="href",
            agent_wallet="W",
            amount_base_units=50_000,
            payer_user_id="u",
        )
        self.svc.refund_escrow("href")
        self.assertEqual(self.svc.get_escrow_status("href"), EscrowStatus.REFUNDED)
        self.assertEqual(self.svc.get_balance_base_units("u"), 1_000_000)

    def test_double_release_fails(self) -> None:
        self.svc.fund_account_usd("u", 1)
        self.svc.fund_escrow(
            hire_id="hdbl",
            agent_wallet="W",
            amount_base_units=10,
            payer_user_id="u",
        )
        self.svc.release_escrow("hdbl")
        with self.assertRaises(PaymentError):
            self.svc.release_escrow("hdbl")

    def test_amount_one_edge(self) -> None:
        self.svc.fund_account_usd("u", 1)
        self.svc.fund_escrow(
            hire_id="hone",
            agent_wallet="W",
            amount_base_units=1,
            payer_user_id="u",
        )
        self.svc.release_escrow("hone")
        self.assertEqual(self.svc.agent_earnings_base_units("W"), 0)
        self.assertEqual(self.svc.store.get_balance("cognilance-treasury"), 1)

    def test_insufficient_balance(self) -> None:
        with self.assertRaises(PaymentError):
            self.svc.fund_escrow(
                hire_id="hx",
                agent_wallet="W",
                amount_base_units=100,
                payer_user_id="broke",
            )


if __name__ == "__main__":
    unittest.main()
