import type { AppIntegration } from "@/types";

export type AppsPanelProps = {
  apps: AppIntegration[];
  onRefresh: () => void;
  onConnect: (appId: string) => void;
};

export function AppsPanel({ apps, onRefresh, onConnect }: AppsPanelProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Apps</h2>
          <button
            type="button"
            onClick={onRefresh}
            className="text-[11px] text-dim hover:text-white"
          >
            Refresh
          </button>
        </div>
        <p className="mt-1 text-[11px] text-dim">Capabilities available to the agent</p>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-3 scrollbar-thin">
        {apps.map((app) => (
          <div
            key={app.id}
            className="rounded-lg border border-border bg-surface p-3 transition-colors hover:border-border/80"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-medium text-white">{app.name}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted">{app.description}</p>
              </div>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                  app.coming_soon
                    ? "border border-border bg-surface text-muted"
                    : app.connected
                      ? "bg-genui/10 text-genui"
                      : "bg-surface text-dim border border-border"
                }`}
              >
                {app.coming_soon ? "soon" : app.connected ? "on" : "off"}
              </span>
            </div>
            {app.coming_soon ? (
              <p className="mt-3 text-xs text-dim">Coming soon</p>
            ) : !app.connected ? (
              <button
                type="button"
                onClick={() => onConnect(app.id)}
                className="mt-3 text-xs text-registry hover:underline"
              >
                Connect
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
