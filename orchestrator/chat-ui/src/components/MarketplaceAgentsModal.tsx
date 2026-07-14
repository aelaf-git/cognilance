import { useCallback, useEffect, useState } from "react";
import { MessageSquare, RefreshCw, X } from "lucide-react";
import type { CatalogAgent } from "@/types";

type MarketplaceAgent = CatalogAgent & {
  id?: string | null;
  description?: string;
  chat_url?: string | null;
  price_usd_cents?: number;
  payout_wallet?: string | null;
};

export function MarketplaceAgentsModal({ onClose }: { onClose: () => void }) {
  const [agents, setAgents] = useState<MarketplaceAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/marketplace/agents");
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(
          String((detail as { detail?: string }).detail ?? `HTTP ${res.status}`),
        );
      }
      const data = await res.json();
      setAgents((data.agents as MarketplaceAgent[]) ?? []);
    } catch (err) {
      setAgents([]);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative flex max-h-[92dvh] w-full max-w-xl flex-col overflow-hidden rounded-t-xl border border-border bg-background shadow-2xl sm:max-h-[88vh] sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="marketplace-title"
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border px-4 py-3 sm:px-5 sm:py-4">
          <div className="min-w-0 pr-2">
            <p
              id="marketplace-title"
              className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted"
            >
              Marketplace agents
            </p>
            <p className="mt-1 text-sm text-white/80">
              Chat directly with a registered agent — opens that agent&apos;s own UI.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void load()}
              className="rounded-md border border-border p-2 text-dim hover:text-white"
              title="Refresh"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border p-2 text-dim hover:text-white"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 scrollbar-thin sm:px-5 sm:py-4">
          {error ? (
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          ) : null}
          {loading && !agents.length ? (
            <p className="text-sm text-muted">Loading agents from the registry…</p>
          ) : null}
          {!loading && !error && !agents.length ? (
            <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted">
              No agents are registered yet. Start them with{" "}
              <code className="text-xs text-white/80">./scripts/start_agents.sh</code>.
            </p>
          ) : null}
          <div className="space-y-2">
            {agents.map((agent) => {
              const chatUrl =
                agent.chat_url ||
                (agent.url ? `${String(agent.url).replace(/\/$/, "")}/chat` : null);
              return (
                <div
                  key={`${agent.id ?? agent.name}-${agent.url ?? ""}`}
                  className="rounded-lg border border-registry/30 bg-registry/[0.06] px-3 py-3"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-white">{agent.name}</p>
                        <span
                          className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                            agent.online
                              ? "border-registry/40 bg-registry/15 text-registry"
                              : "border-border text-dim"
                          }`}
                        >
                          {agent.online ? "online" : "offline"}
                        </span>
                        <span className="rounded-md border border-border px-2 py-0.5 text-[10px] font-semibold text-dim">
                          {(agent.price_usd_cents ?? 0) > 0
                            ? `$${((agent.price_usd_cents ?? 0) / 100).toFixed(2)}`
                            : "Free"}
                        </span>
                      </div>
                      {agent.description ? (
                        <p className="mt-1 text-xs leading-relaxed text-muted">
                          {agent.description}
                        </p>
                      ) : null}
                      {agent.skills?.length ? (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {agent.skills.map((skill) => (
                            <span
                              key={skill}
                              className="rounded-md border border-border px-2 py-0.5 font-mono text-[10px] text-dim"
                            >
                              {skill}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    {chatUrl && agent.online ? (
                      <a
                        href={chatUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex w-full shrink-0 items-center justify-center gap-1.5 rounded-md border border-registry/40 bg-registry/15 px-3 py-2.5 text-xs font-semibold text-registry transition-colors hover:bg-registry/25 sm:w-auto"
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                        Chat with agent
                      </a>
                    ) : (
                      <span className="shrink-0 text-[10px] uppercase tracking-wide text-dim">
                        {agent.online ? "No chat URL" : "Offline"}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
