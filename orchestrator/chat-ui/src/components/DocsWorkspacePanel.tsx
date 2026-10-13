import { useEffect, useRef, useState } from "react";
import type { ActiveDoc } from "@/types";

type DocsWorkspacePanelProps = {
  doc: ActiveDoc;
  onClose: () => void;
  isMobile?: boolean;
};

const LOAD_TIMEOUT_MS = 12_000;

export function DocsWorkspacePanel({ doc, onClose, isMobile }: DocsWorkspacePanelProps) {
  const [blocked, setBlocked] = useState(false);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<number | null>(null);
  const iframeKey = `${doc.document_id}:${doc.revision ?? 0}`;

  useEffect(() => {
    setBlocked(false);
    setLoading(true);
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      // If Google blocks framing, onLoad may never fire usefully — show fallback after timeout
      // while keeping the iframe (some accounts still load slowly).
      setLoading(false);
    }, LOAD_TIMEOUT_MS);
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [iframeKey]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-semibold uppercase tracking-[0.12em] text-muted">
            Google Doc
          </p>
          <p className="truncate text-sm text-white" title={doc.title}>
            {doc.title}
          </p>
        </div>
        <a
          href={doc.url}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 text-xs text-registry hover:underline"
        >
          Open in new tab
        </a>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 rounded px-2 py-1 text-xs text-dim hover:bg-surface hover:text-white"
          aria-label={isMobile ? "Back to chat" : "Close document pane"}
        >
          {isMobile ? "Back" : "Close"}
        </button>
      </div>

      <div className="relative min-h-0 flex-1 bg-black/40">
        {loading ? (
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 px-3 py-2 text-center text-[11px] text-dim">
            Loading Google Doc…
          </div>
        ) : null}

        {blocked ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
            <p className="max-w-sm text-sm text-muted">
              Google blocked embedding this Doc in Cognilance. Open it in a new tab to edit —
              the agent still reads your live Doc before each reply.
            </p>
            <a
              href={doc.url}
              target="_blank"
              rel="noreferrer"
              className="rounded border border-border bg-surface px-3 py-2 text-sm text-white hover:border-white/30"
            >
              Open in Google Docs
            </a>
            <button
              type="button"
              className="text-xs text-dim hover:text-white"
              onClick={() => {
                setBlocked(false);
                setLoading(true);
              }}
            >
              Retry embed
            </button>
          </div>
        ) : (
          <iframe
            key={iframeKey}
            title={doc.title}
            src={doc.url}
            className="h-full w-full border-0 bg-white"
            referrerPolicy="no-referrer-when-downgrade"
            allow="clipboard-read; clipboard-write"
            onLoad={() => {
              setLoading(false);
              if (timerRef.current) window.clearTimeout(timerRef.current);
            }}
            onError={() => {
              setLoading(false);
              setBlocked(true);
            }}
          />
        )}

        {!blocked && !loading ? (
          <div className="absolute bottom-2 left-2 right-2 z-10 rounded border border-border/80 bg-background/90 px-2 py-1.5 text-[11px] text-dim backdrop-blur">
            Edit here anytime. The agent re-reads this Doc before each reply.{" "}
            <button
              type="button"
              className="text-registry hover:underline"
              onClick={() => setBlocked(true)}
            >
              Embed not working?
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function DocsWorkspaceCollapsed({
  title,
  onExpand,
}: {
  title?: string;
  onExpand: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onExpand}
      className="flex h-full w-10 shrink-0 flex-col items-center border-l border-border bg-background py-3 text-dim hover:text-white"
      title={title ? `Show ${title}` : "Show Google Doc"}
      aria-label="Show Google Doc"
    >
      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] [writing-mode:vertical-rl]">
        Doc
      </span>
    </button>
  );
}
