import { useCallback, useEffect, useState } from "react";

type WalletResponse = {
  connected: boolean;
  address?: string;
  provider?: string | null;
  cluster?: string;
  usdc_mint?: string;
  balance_usdc?: number | null;
  spendable_usdc?: number | null;
  balance_error?: string | null;
};

const USDC_FAUCET_URL = "https://faucet.circle.com";

type InjectedProvider = {
  // Phantom resolves with { publicKey }; Solflare resolves with a boolean and
  // exposes the key on provider.publicKey instead.
  connect: () => Promise<{ publicKey?: { toString(): string } } | boolean | void>;
  disconnect?: () => Promise<void>;
  publicKey?: { toString(): string } | null;
};

declare global {
  interface Window {
    solflare?: InjectedProvider & { isSolflare?: boolean };
    phantom?: { solana?: InjectedProvider & { isPhantom?: boolean } };
    solana?: InjectedProvider & { isPhantom?: boolean };
  }
}

function detectProvider(): { name: string; provider: InjectedProvider } | null {
  if (window.solflare?.isSolflare) {
    return { name: "solflare", provider: window.solflare };
  }
  const phantom = window.phantom?.solana ?? window.solana;
  if (phantom?.isPhantom) {
    return { name: "phantom", provider: phantom };
  }
  if (window.solflare) return { name: "solflare", provider: window.solflare };
  if (window.solana) return { name: "solana", provider: window.solana };
  return null;
}

function shortAddress(address: string): string {
  return `${address.slice(0, 4)}…${address.slice(-4)}`;
}

export function WalletBar({ compact = false }: { compact?: boolean }) {
  const [wallet, setWallet] = useState<WalletResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/payments/wallet");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setWallet((await res.json()) as WalletResponse);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Keep the spendable balance live so hire escrows visibly reduce it.
    const timer = setInterval(() => void refresh(), 10_000);
    return () => clearInterval(timer);
  }, [refresh]);

  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      const detected = detectProvider();
      if (!detected) {
        throw new Error(
          "No Solana wallet found. Install Solflare or Phantom (set to Devnet).",
        );
      }
      const result = await detected.provider.connect();
      const address =
        (typeof result === "object" &&
          result !== null &&
          result.publicKey?.toString()) ||
        detected.provider.publicKey?.toString();
      if (!address) throw new Error("Wallet did not return an address");
      const res = await fetch("/payments/wallet/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address, provider: detected.name }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(
          String((detail as { detail?: string }).detail ?? `HTTP ${res.status}`),
        );
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    setError(null);
    try {
      const detected = detectProvider();
      await detected?.provider.disconnect?.().catch(() => undefined);
      await fetch("/payments/wallet/disconnect", { method: "POST" });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const connected = wallet?.connected && wallet.address;

  return (
    <div
      className={`flex flex-wrap items-center gap-1.5 sm:gap-2 ${
        compact ? "w-full" : ""
      }`}
    >
      {connected ? (
        <>
          <span
            className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted"
            title="Solana cluster"
          >
            devnet
          </span>
          <span
            className="font-mono text-[11px] text-white/90 sm:text-xs"
            title={wallet.address}
          >
            {shortAddress(wallet.address!)}
          </span>
          <span
            className="text-[11px] text-muted sm:text-xs"
            title={
              wallet.balance_usdc !== null && wallet.balance_usdc !== undefined
                ? `Spendable hire balance (wallet holds ${wallet.balance_usdc} USDC on devnet)`
                : "Spendable hire balance"
            }
          >
            {wallet.spendable_usdc === null || wallet.spendable_usdc === undefined
              ? "balance —"
              : `$${wallet.spendable_usdc.toFixed(2)} USDC`}
          </span>
          <a
            href={USDC_FAUCET_URL}
            target="_blank"
            rel="noreferrer"
            className="min-h-[32px] rounded-md border border-border px-2 py-1 text-[11px] leading-[22px] text-registry hover:bg-registry/10 sm:text-xs"
            title="Get free devnet USDC from Circle's faucet (select Solana Devnet)"
          >
            Get USDC
          </a>
          <button
            type="button"
            disabled={busy}
            onClick={() => void refresh()}
            className="min-h-[32px] rounded-md border border-border px-2 py-1 text-[11px] text-muted hover:text-white disabled:opacity-50 sm:text-xs"
            title="Refresh balance"
          >
            Refresh
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void disconnect()}
            className="min-h-[32px] rounded-md border border-border px-2 py-1 text-[11px] text-muted hover:text-white disabled:opacity-50 sm:text-xs"
          >
            Disconnect
          </button>
        </>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={() => void connect()}
          className="min-h-[32px] rounded-md border border-registry/60 px-2.5 py-1 text-[11px] font-medium text-registry hover:bg-registry/10 disabled:opacity-50 sm:text-xs"
          title="Connect a Solana wallet (Solflare or Phantom, Devnet)"
        >
          {busy ? "Connecting…" : "Connect wallet"}
        </button>
      )}
      {error ? (
        <span className="w-full text-[10px] text-red-400 sm:w-auto">{error}</span>
      ) : null}
    </div>
  );
}
