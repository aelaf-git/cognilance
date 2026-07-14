"""Payment configuration (env-driven)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PaymentConfig:
    """When enabled, managers fund escrow on paid hires and settle after validation.

    Mock mode (default): integer balances and escrow links in a local SQLite
    ledger that mirrors cognilance_escrow semantics (90/10 release). No Solana
    RPC required — used for product e2e and for custom managers in tests.

    Chain mode: set PAYMENTS_USE_CHAIN=1 once the Solana IDL client is wired.
    Until then, that flag raises NotImplementedError — keep the mock ledger.
    """

    enabled: bool = True
    rpc_url: str = "http://localhost:8899"
    mock_usdc_mint: str | None = None
    treasury_wallet: str | None = None
    authority_keypair_path: str | None = None
    faucet_keypair_path: str | None = None
    db_path: Path | None = None
    # When True (default), use the in-process mock ledger even if RPC is set.
    # Set PAYMENTS_USE_CHAIN=1 to prefer on-chain submission.
    use_mock_ledger: bool = True

    @classmethod
    def from_env(cls, *, enabled: bool | None = None) -> PaymentConfig:
        env_enabled = os.environ.get("PAYMENTS_ENABLED", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }
        use_chain = os.environ.get("PAYMENTS_USE_CHAIN", "").strip() in {
            "1",
            "true",
            "True",
            "yes",
        }
        db = os.environ.get("PAYMENTS_DB_PATH")
        return cls(
            enabled=env_enabled if enabled is None else enabled,
            rpc_url=os.environ.get("SOLANA_RPC_URL", "http://localhost:8899"),
            mock_usdc_mint=os.environ.get("MOCK_USDC_MINT") or None,
            treasury_wallet=os.environ.get("TREASURY_WALLET") or None,
            authority_keypair_path=os.environ.get("BACKEND_AUTHORITY_KEYPAIR_PATH")
            or None,
            faucet_keypair_path=os.environ.get("FAUCET_KEYPAIR_PATH") or None,
            db_path=Path(db) if db else None,
            use_mock_ledger=not use_chain,
        )

    @classmethod
    def disabled(cls) -> PaymentConfig:
        return cls(enabled=False)
