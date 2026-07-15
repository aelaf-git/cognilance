import { useCallback, useEffect, useState } from "react";
import { Wallet, RefreshCw } from "lucide-react";
import { fetchEarnings, type EarningsResponse } from "../api";

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

const WALLET_STORAGE_KEY = "cognilance-dev-wallet";

export function EarningsPanel() {
  const [wallet, setWallet] = useState<string>(
    () => localStorage.getItem(WALLET_STORAGE_KEY) ?? "",
  );
  const [data, setData] = useState<EarningsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (address: string) => {
    if (!address.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setData(await fetchEarnings(address.trim()));
    } catch (exc) {
      setData(null);
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (wallet) void load(wallet);
  }, [wallet, load]);

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
      localStorage.setItem(WALLET_STORAGE_KEY, address);
      setWallet(address);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    const detected = detectProvider();
    await detected?.provider.disconnect?.().catch(() => undefined);
    localStorage.removeItem(WALLET_STORAGE_KEY);
    setWallet("");
    setData(null);
    setError(null);
  };

  return (
    <div className="mb-8 rounded-xl border border-border bg-surface/40 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-medium text-white">Payouts / earnings</h2>
        <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted">
          devnet
        </span>
        <div className="ml-auto flex items-center gap-2">
          {wallet ? (
            <>
              <span className="font-mono text-xs text-white/90" title={wallet}>
                {shortAddress(wallet)}
              </span>
              <button
                type="button"
                disabled={busy}
                onClick={() => void load(wallet)}
                className="rounded-md border border-border px-2 py-1 text-xs text-muted hover:text-white disabled:opacity-50"
                title="Refresh earnings"
              >
                <RefreshCw className="inline h-3 w-3" />
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void disconnect()}
                className="rounded-md border border-border px-2.5 py-1 text-xs text-muted hover:text-white disabled:opacity-50"
              >
                Disconnect
              </button>
            </>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => void connect()}
              className="flex items-center gap-1.5 rounded-md border border-registry/40 bg-registry/15 px-3 py-1.5 text-xs font-semibold text-registry hover:bg-registry/25 disabled:opacity-50"
              title="Connect your payout wallet (Solflare or Phantom, Devnet)"
            >
              <Wallet className="h-3.5 w-3.5" />
              {busy ? "Connecting…" : "Connect wallet"}
            </button>
          )}
        </div>
      </div>
      <p className="mt-1 text-xs text-muted">
        Connect the wallet you set as <code className="text-white/80">PAYOUT_WALLET</code> on
        your agents. You earn 90% of each settled hire.
      </p>
      {error ? <p className="mt-2 text-xs text-red-400">{error}</p> : null}

      {data ? (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <div className="rounded-lg border border-border bg-background px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-dim">Total hires</p>
              <p className="mt-0.5 text-lg font-semibold text-white">{data.total_hires}</p>
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-dim">Total earned</p>
              <p className="mt-0.5 text-lg font-semibold text-white">
                ${data.total_earned_usd.toFixed(2)}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-background px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-dim">
                Collectable balance
              </p>
              <p className="mt-0.5 text-lg font-semibold text-white">
                ${data.balance_usd.toFixed(2)}
              </p>
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
              My agents
            </h3>
            {data.agents.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[36rem] text-left text-xs">
                  <thead>
                    <tr className="border-b border-border text-[10px] uppercase tracking-wide text-dim">
                      <th className="py-1.5 pr-3 font-medium">Agent</th>
                      <th className="py-1.5 pr-3 font-medium">Skill</th>
                      <th className="py-1.5 pr-3 font-medium">Price / hire</th>
                      <th className="py-1.5 pr-3 font-medium">Status</th>
                      <th className="py-1.5 pr-3 font-medium">Hires</th>
                      <th className="py-1.5 font-medium">Earned</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.agents.map((agent) => (
                      <tr key={agent.id ?? agent.name} className="border-b border-border/50">
                        <td className="py-2 pr-3 font-medium text-white">{agent.name}</td>
                        <td className="py-2 pr-3 font-mono text-muted">
                          {agent.skills.join(", ")}
                        </td>
                        <td className="py-2 pr-3 text-white/90">
                          {agent.price_usd_cents > 0
                            ? `$${(agent.price_usd_cents / 100).toFixed(2)}`
                            : "Free"}
                        </td>
                        <td className="py-2 pr-3">
                          <span
                            className={`flex items-center gap-1.5 ${
                              agent.online ? "text-registry" : "text-dim"
                            }`}
                          >
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${
                                agent.online ? "bg-registry" : "bg-red-500/80"
                              }`}
                            />
                            {agent.online ? "online" : "offline"}
                          </span>
                        </td>
                        <td className="py-2 pr-3 font-mono text-white/90">{agent.hires}</td>
                        <td className="py-2 font-mono text-white/90">
                          ${agent.earned_usd.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-dim">
                No registry agents use this wallet as PAYOUT_WALLET yet.
              </p>
            )}
          </div>

          {data.ledger.length ? (
            <div>
              <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">
                Recent payouts
              </h3>
              <ul className="max-h-40 space-y-1 overflow-y-auto text-[11px] text-muted">
                {data.ledger.map((row, i) => (
                  <li key={`${row.created_at}-${i}`} className="font-mono">
                    {row.created_at.slice(0, 19)} · +${(row.amount / 1_000_000).toFixed(2)}
                    {row.hire_id ? ` · ${row.hire_id.slice(0, 18)}…` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : wallet ? (
        <p className="mt-3 text-xs text-dim">{busy ? "Loading…" : "No data yet."}</p>
      ) : null}
    </div>
  );
}
