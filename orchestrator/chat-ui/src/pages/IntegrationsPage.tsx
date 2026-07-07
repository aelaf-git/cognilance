import type { AppIntegration } from "@/types";

const LOGO_STYLES: Record<string, { bg: string; label: string }> = {
  drive: { bg: "bg-blue-500/20 text-blue-400", label: "GD" },
  gmail: { bg: "bg-red-500/20 text-red-400", label: "GM" },
  calendar: { bg: "bg-sky-500/20 text-sky-400", label: "GC" },
  notion: { bg: "bg-white/10 text-white", label: "N" },
  slack: { bg: "bg-purple-500/20 text-purple-300", label: "S" },
  github: { bg: "bg-zinc-500/20 text-zinc-200", label: "GH" },
};

export function IntegrationLogo({ logo }: { logo: string }) {
  const style = LOGO_STYLES[logo] ?? { bg: "bg-surface text-muted", label: "?" };
  return (
    <div
      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${style.bg}`}
    >
      {style.label}
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
      <header className="flex shrink-0 items-center gap-4 border-b border-border px-6 py-4">
        <img src="/logo.png" alt="Cognilance" className="h-7 w-auto object-contain" />
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Integrations
          </p>
          <p className="text-sm text-dim">Connect apps for the orchestrator agent</p>
        </div>
        <a href="/chat" className="ml-auto text-xs text-registry hover:underline">
          Back to chat
        </a>
      </header>

      <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
        {banner ? (
          <div className="mb-4 rounded-lg border border-registry/30 bg-registry/10 px-4 py-3 text-sm text-registry">
            {banner}
          </div>
        ) : null}

        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm text-muted">
            OAuth connections — tokens are stored encrypted server-side and never shown here.
          </p>
          <button
            type="button"
            onClick={onRefresh}
            className="text-xs text-dim hover:text-white"
          >
            Refresh
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
                        item.connected
                          ? "bg-genui/10 text-genui"
                          : "bg-background text-dim border border-border"
                      }`}
                    >
                      {item.connected ? "Connected" : "Disconnected"}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{item.description}</p>
                  {item.actions?.length ? (
                    <p className="mt-2 text-[11px] text-dim">
                      Agent actions: {item.actions.join(", ")}
                    </p>
                  ) : null}
                </div>
              </div>
              <div className="mt-4">
                {item.connected ? (
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
