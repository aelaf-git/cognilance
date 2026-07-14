"""Payment domain models (integer base units only)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


USDC_DECIMALS = 6
USDC_BASE_UNITS_PER_USD = 10**USDC_DECIMALS


class EscrowStatus(str, Enum):
    FUNDED = "funded"
    RELEASED = "released"
    REFUNDED = "refunded"


class LedgerEntryType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


@dataclass
class HirePayment:
    """Handle returned from a paid hire; pass to settle_hire / refund_hire."""

    hire_id: str
    on_chain_task_id: int
    agent_id: str | None
    agent_wallet: str
    amount_base_units: int
    mission_id: str | None = None
    payer_user_id: str | None = None
    status: EscrowStatus = EscrowStatus.FUNDED
    tx_signature: str | None = None


def usd_to_base_units(amount_usd: int) -> int:
    """Whole USD dollars → USDC base units (1 USD = 1_000_000)."""
    if amount_usd < 0:
        raise ValueError("amount_usd must be non-negative")
    return amount_usd * USDC_BASE_UNITS_PER_USD


def cents_to_base_units(cents: int) -> int:
    """USD cents → USDC base units (100 cents = 1_000_000 base units)."""
    if cents < 0:
        raise ValueError("cents must be non-negative")
    return cents * (USDC_BASE_UNITS_PER_USD // 100)
