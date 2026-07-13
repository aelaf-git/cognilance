import { FeedCardView } from "@/components/FeedCard";
import { PROCESS_CARD_TYPES } from "@/lib/sessionEvents";
import type { OrchestrationTurn, SessionSummary } from "@/types";
import { CARD_META } from "@/types";

export function isProcessingSession(session: SessionSummary): boolean {
  return (
    session.display_status === "processing" ||
    (session.listener_active === true &&
      (session.status === "running" || session.status === "queued"))
  );
}

export function sessionStatusLabel(session: SessionSummary): string {
  if (isProcessingSession(session)) return "Processing…";
  if (session.display_status === "done" || session.status === "completed") return "Done";
  if (session.display_status === "aborted" || session.status === "cancelled") return "Aborted";
  if (session.display_status === "failed" || session.status === "failed") return "Failed";
  if (session.status === "running" || session.status === "queued") return "Running";
  return session.status;
}

function statusAccent(session: SessionSummary): string {
  if (isProcessingSession(session) || session.status === "running" || session.status === "queued") {
    return "border-l-planner";
  }
  if (session.status === "failed") return "border-l-red-500";
  if (session.status === "cancelled") return "border-l-task";
  return "border-l-registry";
}

export function SessionDetailCollapsed({ onExpand }: { onExpand: () => void }) {
  return (
    <div className="flex h-full w-10 shrink-0 flex-col border-l border-border bg-background">
      <button
        type="button"
        onClick={onExpand}
        title="Show sessions"
        className="flex h-12 w-full items-center justify-center text-muted hover:bg-surface hover:text-white"
      >
        <PanelIcon />
      </button>
    </div>
  );
}

export function SessionListPanel({
  sessions,
  onSelectSession,
  onAbortSession,
  onCollapse,
}: {
  sessions: SessionSummary[];
  onSelectSession: (sessionId: string) => void;
  onAbortSession: (sessionId: string) => void;
  onCollapse: () => void;
}) {
  return (
    <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col bg-background">
      <div className="flex shrink-0 items-center justify-between border-b border-border px-3 py-2.5">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Sessions
          </p>
          <p className="mt-0.5 text-xs text-dim">
            {sessions.length === 0
              ? "No sessions"
              : `${sessions.length} session${sessions.length === 1 ? "" : "s"}`}
          </p>
        </div>
        <button
          type="button"
          onClick={onCollapse}
          title="Hide sessions"
          className="shrink-0 rounded p-1.5 text-dim hover:bg-surface hover:text-white"
        >
          <PanelIcon />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3 scrollbar-thin">
        {sessions.length === 0 ? (
          <p className="px-1 text-xs text-dim">No sessions yet. Send a message to start one.</p>
        ) : (
          <div className="space-y-2">
            {sessions.map((session, index) => {
              const processing = isProcessingSession(session);
              return (
                <div
                  key={session.id}
                  className={`rounded-lg border border-border bg-surface/60 px-3 py-2.5 border-l-[3px] ${statusAccent(session)}`}
                >
                  <button
                    type="button"
                    onClick={() => onSelectSession(session.id)}
                    className="w-full text-left"
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">
                      Session {index + 1}
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs text-white">{session.instruction}</p>
                    <span className="mt-2 inline-block text-[10px] uppercase tracking-wide text-dim">
                      {sessionStatusLabel(session)}
                    </span>
                  </button>
                  {processing ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onAbortSession(session.id);
                      }}
                      className="mt-2 text-[10px] uppercase tracking-wide text-dim hover:text-red-400"
                    >
                      Abort
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export function SessionDetailModal({
  session,
  turn,
  onClose,
  onAbort,
}: {
  session: SessionSummary;
  turn: OrchestrationTurn | null;
  onClose: () => void;
  onAbort: (sessionId: string) => void;
}) {
  const processCards =
    turn?.cards.filter((c) => PROCESS_CARD_TYPES.includes(c.type)) ?? [];
  const canAbort = isProcessingSession(session);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="relative flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-detail-title"
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border bg-gradient-to-b from-surface/80 to-background px-5 py-4 pr-12">
          <div className="min-w-0">
            <p
              id="session-detail-title"
              className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted"
            >
              Session detail
            </p>
            <p className="mt-1 text-sm leading-relaxed text-white">{session.instruction}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="inline-flex rounded-md border border-border bg-background/80 px-2 py-0.5 text-[10px] uppercase tracking-wide text-dim">
                {sessionStatusLabel(session)}
              </span>
              {processCards.length > 0 ? (
                <span className="text-[10px] text-dim">
                  {processCards.length} step{processCards.length === 1 ? "" : "s"}
                </span>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            title="Close"
            className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-md text-dim hover:bg-surface hover:text-white"
          >
            <CloseIcon />
          </button>
        </div>

        {canAbort ? (
          <div className="shrink-0 border-b border-border px-5 py-2">
            <button
              type="button"
              onClick={() => onAbort(session.id)}
              className="text-xs text-dim hover:text-red-400"
            >
              Abort
            </button>
          </div>
        ) : null}

        <div className="min-h-0 flex-1 overflow-y-auto p-5 scrollbar-thin">
          {processCards.length === 0 ? (
            <p className="text-xs text-dim">
              {isProcessingSession(session)
                ? "Listening in the background — you can keep chatting."
                : session.status === "running" || session.status === "queued"
                  ? "Waiting for process events…"
                  : "No process steps recorded."}
            </p>
          ) : (
            <div className="relative space-y-4">
              <div
                className="absolute bottom-4 left-[7px] top-4 w-px bg-gradient-to-b from-planner/50 via-registry/30 to-genui/40"
                aria-hidden
              />
              {processCards.map((card, i) => (
                <div key={card.id} className="relative pl-6">
                  <span
                    className="absolute left-0 top-5 h-3.5 w-3.5 rounded-full border-2 border-background"
                    style={{ backgroundColor: CARD_META[card.type].accent }}
                  />
                  <FeedCardView card={card} index={i} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PanelIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M15 3v18" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}
