import { useState } from "react";
import type { AppIntegration } from "@/types";

/** Fallback initials when an image fails to load. */
const LOGO_FALLBACK: Record<string, { bg: string; label: string }> = {
  drive: { bg: "bg-blue-500/20 text-blue-400", label: "GD" },
  gmail: { bg: "bg-red-500/20 text-red-400", label: "GM" },
  calendar: { bg: "bg-sky-500/20 text-sky-400", label: "GC" },
  notion: { bg: "bg-white/10 text-white", label: "N" },
  slack: { bg: "bg-purple-500/20 text-purple-300", label: "S" },
  github: { bg: "bg-zinc-500/20 text-zinc-200", label: "GH" },
};

export function IntegrationLogo({ logo }: { logo: string }) {
  const id = logo.trim().toLowerCase();
  const fallback = LOGO_FALLBACK[id] ?? { bg: "bg-surface text-muted", label: "?" };
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${fallback.bg}`}
      >
        {fallback.label}
      </div>
    );
  }

  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border bg-white/5 p-1.5">
      <img
        src={`/integrations/logos/${encodeURIComponent(id)}`}
        alt=""
        className="h-full w-full object-contain"
        loading="lazy"
        onError={() => setFailed(true)}
      />
    </div>
  );
}

export type IntegrationsPageProps = {
  integrations: AppIntegration[];
  onRefresh: () => void;
  onConnect: (id: string) => void;
  onDisconnect: (id: string) => void;
  banner?: string | null;
};

export function IntegrationsPage({
  integrations,
  onRefresh,
  onConnect,
  onDisconnect,
  banner,
}: IntegrationsPageProps) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <header className="flex shrink-0 flex-wrap items-center gap-3 border-b border-border px-4 py-3 sm:gap-4 sm:px-6 sm:py-4">
        <img src="/icon.png" alt="Cognilance" className="h-6 w-6 object-contain sm:h-7 sm:w-7" />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Integrations
          </p>
          <p className="text-sm text-dim">Connect apps for the orchestrator agent</p>
        </div>
        <a href="/chat" className="text-xs text-registry hover:underline sm:ml-auto">
          Back to chat
        </a>
      </header>

      <div className="flex-1 overflow-y-auto p-4 scrollbar-thin sm:p-6">
        {banner ? (
          <div className="mb-4 rounded-lg border border-registry/30 bg-registry/10 px-4 py-3 text-sm text-registry">
            {banner}
          </div>
        ) : null}

        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted">
            OAuth connections — tokens are stored encrypted server-side and never shown here.
          </p>
          <button
            type="button"
            onClick={onRefresh}
            className="self-start text-xs text-dim hover:text-white"
          >
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {integrations.map((item) => (
            <div
              key={item.id}
              className="flex flex-col rounded-xl border border-border bg-surface/40 p-5"
            >
              <div className="flex items-start gap-3">
                <IntegrationLogo logo={item.logo ?? item.id} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-medium text-white">{item.name}</h3>
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                        item.coming_soon
                          ? "border border-border bg-background text-muted"
                          : item.connected
                            ? "bg-genui/10 text-genui"
                            : "border border-border bg-background text-dim"
                      }`}
                    >
                      {item.coming_soon
                        ? "Coming soon"
                        : item.connected
                          ? "Connected"
                          : "Disconnected"}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{item.description}</p>
                  {!item.coming_soon && item.actions?.length ? (
                    <p className="mt-2 text-[11px] text-dim">
                      Agent actions: {item.actions.join(", ")}
                    </p>
                  ) : null}
                </div>
              </div>
              <div className="mt-4">
                {item.coming_soon ? (
                  <span className="text-xs text-dim">Coming soon</span>
                ) : item.connected ? (
                  <button
                    type="button"
                    onClick={() => onDisconnect(item.id)}
                    className="rounded-md border border-border px-3 py-1.5 text-xs text-dim hover:border-red-500/40 hover:text-red-400"
                  >
                    Disconnect
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => onConnect(item.id)}
                    className="rounded-md bg-registry/20 px-3 py-1.5 text-xs font-medium text-registry hover:bg-registry/30"
                  >
                    Connect
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
