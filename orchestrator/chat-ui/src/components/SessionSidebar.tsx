import type { SessionSummary } from "@/types";

export function canDismissSession(session: SessionSummary): boolean {
  if (session.status === "running" || session.status === "queued") return false;
  if (session.session_type === "recurring") {
    return session.status === "cancelled" || session.status === "failed";
  }
  return session.status === "completed" || session.status === "failed" || session.status === "cancelled";
}

function sessionStatusLabel(session: SessionSummary): string {
  if (session.session_type === "recurring") {
    if (session.status === "cancelled") return "Aborted";
    if (session.status === "failed") return "Failed";
    if (session.status === "running" || session.status === "queued") return "Active";
    return "Active";
  }
  const labels: Record<string, string> = {
    queued: "Queued",
    running: "Running",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Aborted",
  };
  return labels[session.status] ?? session.status;
}

export function SessionSidebarCollapsed({ onExpand }: { onExpand: () => void }) {
  return (
    <div className="flex h-full w-10 shrink-0 flex-col border-r border-border bg-background">
      <button
        type="button"
        onClick={onExpand}
        title="Show sessions"
        className="flex h-12 w-full items-center justify-center text-muted hover:bg-surface hover:text-white"
      >
        <MenuIcon />
      </button>
    </div>
  );
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  onCollapse,
  onSelect,
  onAbort,
  onDismiss,
}: {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onCollapse: () => void;
  onSelect: (sessionId: string) => void;
  onAbort: (sessionId: string) => void;
  onDismiss: (sessionId: string) => void;
}) {
  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col bg-background">
      <div className="flex shrink-0 items-center justify-between border-b border-border px-3 py-2.5">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
          Sessions
        </h3>
        <button
          type="button"
          onClick={onCollapse}
          title="Hide sessions"
          className="rounded p-1.5 text-dim hover:bg-surface hover:text-white"
        >
          <MenuIcon />
        </button>
      </div>
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3 scrollbar-thin">
        {sessions.length === 0 ? (
          <p className="text-xs text-dim">No sessions yet.</p>
        ) : (
          sessions.map((session) => {
            const active = activeSessionId === session.id;
            const isRecurring = session.session_type === "recurring";
            const canAbort =
              isRecurring &&
              (session.status === "running" || session.status === "queued");
            const canDismiss = canDismissSession(session);
            return (
              <div
                key={session.id}
                className={`rounded-lg border transition-colors ${
                  active
                    ? "border-registry/40 bg-registry/10"
                    : "border-border bg-surface/60 hover:border-border/80"
                }`}
              >
                <div className="flex items-start gap-1">
                  <button
                    type="button"
                    onClick={() => onSelect(session.id)}
                    className="min-w-0 flex-1 px-2.5 py-2 text-left"
                  >
                    <p className="truncate text-xs text-white">{session.instruction}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-[10px] uppercase tracking-wide text-muted">
                        {sessionStatusLabel(session)}
                      </span>
                      {isRecurring ? (
                        <span className="rounded bg-thinking/10 px-1 py-0.5 text-[9px] uppercase text-thinking">
                          recurring
                        </span>
                      ) : null}
                    </div>
                  </button>
                  {canDismiss ? (
                    <button
                      type="button"
                      title="Remove from list"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDismiss(session.id);
                      }}
                      className="mr-2 mt-2 shrink-0 rounded p-1 text-dim hover:bg-red-500/10 hover:text-red-400"
                    >
                      <TrashIcon />
                    </button>
                  ) : null}
                </div>
                {canAbort ? (
                  <div className="border-t border-border px-2.5 py-1.5">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onAbort(session.id);
                      }}
                      className="text-[10px] text-dim hover:text-red-400"
                    >
                      Abort
                    </button>
                  </div>
                ) : null}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
    </svg>
  );
}
