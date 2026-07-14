import { useState } from "react";
import { fetchEarnings, type EarningsResponse } from "../api";

export function EarningsPanel() {
  const [wallet, setWallet] = useState("");
  const [data, setData] = useState<EarningsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    if (!wallet.trim()) {
      setError("Enter your payout wallet pubkey");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setData(await fetchEarnings(wallet.trim()));
    } catch (exc) {
      setData(null);
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mb-8 rounded-xl border border-border bg-surface/40 p-4">
      <h2 className="text-sm font-medium text-white">Collect / earnings</h2>
      <p className="mt-1 text-xs text-muted">
        Funds arrive automatically when managers settle hires (90% to your wallet). Set{" "}
        <code className="text-white/80">PAYOUT_WALLET</code> and{" "}
        <code className="text-white/80">PRICE_USD_CENTS</code> in the agent env before start.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <input
          value={wallet}
          onChange={(e) => setWallet(e.target.value)}
          placeholder="Payout wallet (base58 pubkey)"
          className="w-full min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2.5 font-mono text-xs text-white sm:min-w-[12rem] sm:py-2"
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => void load()}
          className="w-full rounded-md border border-registry/40 bg-registry/15 px-3 py-2.5 text-xs font-semibold text-registry hover:bg-registry/25 disabled:opacity-50 sm:w-auto sm:py-2"
        >
          {busy ? "Loading…" : "View balance"}
        </button>
      </div>
      {error ? <p className="mt-2 text-xs text-red-400">{error}</p> : null}
      {data ? (
        <div className="mt-3 space-y-2">
          <p className="text-sm text-white">
            Balance:{" "}
            <span className="font-mono">
              {data.balance_base_units} base units (${data.balance_usd} mock USDC)
            </span>
          </p>
          <p className="text-[11px] text-dim">{data.note}</p>
          {data.ledger.length ? (
            <ul className="max-h-40 space-y-1 overflow-y-auto text-[11px] text-muted">
              {data.ledger.map((row, i) => (
                <li key={`${row.created_at}-${i}`} className="font-mono">
                  {row.created_at} · {row.entry_type} · {row.amount}
                  {row.hire_id ? ` · ${row.hire_id}` : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-dim">No ledger entries yet.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
