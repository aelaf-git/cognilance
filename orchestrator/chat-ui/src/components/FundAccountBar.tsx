import { useCallback, useEffect, useState } from "react";

type BalanceResponse = {
  balance_base_units: number;
  balance_usd: number;
  wallet_id: string;
};

export function FundAccountBar({ compact = false }: { compact?: boolean }) {
  const [balanceUsd, setBalanceUsd] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/payments/balance");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as BalanceResponse;
      setBalanceUsd(data.balance_usd);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const fund = async (amountUsd: number) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/payments/fund", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount_usd: amountUsd }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(
          String((detail as { detail?: string }).detail ?? `HTTP ${res.status}`),
        );
      }
      const data = (await res.json()) as BalanceResponse;
      setBalanceUsd(data.balance_usd);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={`flex flex-wrap items-center gap-1.5 sm:gap-2 ${
        compact ? "w-full" : ""
      }`}
    >
      <span
        className="text-[11px] text-muted sm:text-xs"
        title="Mock USDC balance (1 USD = 1 USDC)"
      >
        {compact ? "$" : "Balance: $"}
        <span className="font-mono text-white/90">
          {balanceUsd === null ? "…" : balanceUsd}
        </span>
      </span>
      <button
        type="button"
        disabled={busy}
        onClick={() => void fund(10)}
        className="min-h-[32px] rounded-md border border-border px-2 py-1 text-[11px] text-registry hover:bg-registry/10 disabled:opacity-50 sm:text-xs"
        title="Mock fund: mint $10 mock USDC (no real card)"
      >
        {compact ? "+$10" : "Fund $10"}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => void fund(50)}
        className="min-h-[32px] rounded-md border border-border px-2 py-1 text-[11px] text-registry hover:bg-registry/10 disabled:opacity-50 sm:text-xs"
      >
        {compact ? "+$50" : "Fund $50"}
      </button>
      {error ? <span className="w-full text-[10px] text-red-400 sm:w-auto">{error}</span> : null}
    </div>
  );
}
