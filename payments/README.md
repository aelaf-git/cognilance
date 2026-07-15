# Cognilance Payments — Solana Escrow Workspace

Anchor workspace for `cognilance_escrow`, the on-chain USDC escrow that holds a
consumer's payment per task and releases it 90/10 (agent/platform) or refunds
it in full, gated by a single backend authority key.

## Layout

- `programs/cognilance_escrow/` — the Anchor program (state, instructions, errors, events)
- `scripts/create-mock-usdc.ts` — creates a 6-decimal mock USDC mint for local/devnet testing
- `tests/cognilance_escrow.ts` — TypeScript test suite (happy path, refund, auth failures, rounding edge cases)
- `backend/payment_service.py` — thin re-export of `cognilance.payments.PaymentService` (real logic is in the SDK)
- `.env.example` — configuration template

## Toolchain

| Tool | Version used | Notes |
| --- | --- | --- |
| Rust | 1.97 (stable) | via rustup |
| Solana CLI (Agave) | 3.1.10 | includes `solana-test-validator` |
| Anchor CLI | 1.1.2 | via `avm install 1.1.2 && avm use 1.1.2` |
| `@anchor-lang/core` | 1.1.2 | Anchor 1.x renamed the npm package from `@coral-xyz/anchor` |
| `@solana/web3.js` | 1.x | the Anchor TS client requires 1.x, not the 2.x rewrite |
| `@solana/spl-token` | 0.4.x | |
| Node.js | 20+ | |

Version pinning notes for local testing:

- The Anchor CLI and `@anchor-lang/core` must be the same version (both 1.1.2 here).
- Anchor 1.x defaults `anchor test` to the Surfpool validator. This workspace
  uses the classic `solana-test-validator` via the `--validator legacy` flag
  (the validator choice is CLI-flag only in this Anchor version; it cannot be
  set in `Anchor.toml`).
- Program ID is declared in `programs/cognilance_escrow/src/lib.rs`. After a
  fresh keypair (`anchor keys list` / deploy), update `declare_id!` and
  `Anchor.toml` to match. The deploy keypair lives under `target/deploy/`
  (gitignored) — do not commit it; regenerate and sync IDs if missing.

## Running locally

### 1. Build the program

```bash
cd payments
npm install
anchor build
```

### 2. Run the test suite (recommended first step)

`anchor test` starts its own local validator, deploys the program, and runs
`tests/cognilance_escrow.ts`. Nothing else needs to be running (stop any
validator already bound to port 8899 first):

```bash
anchor test --validator legacy
```

The suite covers: 90/10 split correctness (including non-round amounts like
101 → 90/11 and amount = 1 → 0/1), full refunds, non-authority rejection,
double-release rejection, and release-after-refund rejection. All assertions
are in integer base units.

### 3. Run a standalone local validator + mock USDC

For manual poking or backend development:

```bash
# Terminal 1: local validator with a fresh ledger
solana-test-validator --reset

# Terminal 2: create the mock USDC mint and fund test wallets
cd payments
npx ts-node scripts/create-mock-usdc.ts            # generates 3 test wallets
# or mint to specific wallets:
npx ts-node scripts/create-mock-usdc.ts <PUBKEY1> <PUBKEY2>
```

The script prints the mint address — copy it into `.env` as `MOCK_USDC_MINT`.

Deploy the program to the running validator with:

```bash
anchor deploy
```

Then call `initialize_program` once (from a script or the backend) with the
backend authority and treasury pubkeys before creating any escrows.

### 4. Configure

```bash
cp .env.example .env
# fill in MOCK_USDC_MINT, TREASURY_WALLET, BACKEND_AUTHORITY_KEYPAIR_PATH
```

## Pointing at devnet later

The same code runs on devnet unchanged; only configuration moves:

1. Swap the RPC URL in `.env`:
   `SOLANA_RPC_URL=https://api.devnet.solana.com`
2. Point the Solana CLI at devnet and fund the deploy wallet:

```bash
solana config set --url devnet
solana airdrop 2
```

3. Deploy and re-run the mock USDC script against devnet (real USDC does not
   exist on devnet, so the mock mint is used there too):

```bash
anchor deploy --provider.cluster devnet
SOLANA_RPC_URL=https://api.devnet.solana.com npx ts-node scripts/create-mock-usdc.ts
```

4. Update `[programs.localnet]` / provider cluster in `Anchor.toml` (or pass
   `--provider.cluster devnet` per command) and set the new `MOCK_USDC_MINT`
   in `.env`. On mainnet, `MOCK_USDC_MINT` is replaced by the real USDC mint
   (`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`).

## Program design notes

- One `EscrowAccount` PDA per task, seeds `["escrow", task_id (u64 LE)]`; the
  token vault is an associated token account owned by the escrow PDA.
- Treasury and authority are fixed once in a global `Config` PDA
  (`initialize_program`) and copied into each escrow — they are never accepted
  as instruction arguments, so no caller can redirect funds.
- `release_escrow` computes `agent_cut = amount * 90 / 100` in integer math
  and gives `platform_cut = amount - agent_cut` (the remainder) to the
  platform, so the two cuts always sum exactly to `amount`.
- Both `release_escrow` and `refund_escrow` require status `Funded` and flip
  it in the same transaction, so each escrow settles exactly once.
- `EscrowReleased` / `EscrowRefunded` Anchor events are emitted for backend
  indexing into the `ledger_entries` mirror table.

## Product integration (SDK + orchestrator)

The shared runtime is `cognilance.payments.PaymentService` (mock ledger by
default at `~/.cognilance/payments.db`). `CognilanceManager.hire` funds escrow
when `price_usd_cents > 0`; managers must call `settle_hire` / `refund_hire`
after validation (the orchestrator does this in mission finalize).

Orchestrator chat UI: **Connect wallet** (Solflare or Phantom, Devnet) →
`POST /payments/wallet/connect` links the address to the user; the header shows
the devnet **USDC** balance (`GET /payments/wallet`, summed over the owner's
token accounts for the configured mint). The mint defaults to Circle's devnet
USDC (`4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU`) — get free test USDC at
https://faucet.circle.com — or set `MOCK_USDC_MINT` to a self-minted mock USDC
created with `scripts/create-mock-usdc.ts`. A 1 SOL devnet airdrop endpoint
(`POST /payments/wallet/airdrop`) exists for future tx fees. The mock-USDC
`POST /payments/fund` endpoint still exists for tests/scripts but has no UI
button anymore.
Developer portal: set `PAYOUT_WALLET` + `PRICE_USD_CENTS` on agent env; use
**Collect / earnings** to view settled balances.

