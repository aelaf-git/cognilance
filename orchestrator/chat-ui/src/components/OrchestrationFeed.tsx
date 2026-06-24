import { useEffect, useRef } from "react";
import { FeedCardView } from "@/components/FeedCard";
import type { OrchestrationTurn } from "@/types";

export function OrchestrationFeed({
  turns,
  statusMessage,
}: {
  turns: OrchestrationTurn[];
  statusMessage: string | null;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onScroll = () => {
      const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickRef.current = gap < 96;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (stickRef.current) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, statusMessage]);

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto scrollbar-thin">
      <div className="mx-auto max-w-4xl space-y-8 px-5 py-6">
        {turns.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-surface/40 px-6 py-12 text-center">
            <p className="text-sm font-medium text-white/90">Orchestration feed</p>
            <p className="mt-2 text-sm text-muted">
              Send a prompt to watch the planner, routing, agent execution, and generative UI
              unfold in real time.
            </p>
          </div>
        ) : (
          turns.map((turn) => (
            <section key={turn.id} className="space-y-3">
              {turn.cards.map((card, i) => (
                <FeedCardView key={card.id} card={card} index={i} />
              ))}
            </section>
          ))
        )}
        {statusMessage ? (
          <div className="flex items-center gap-2 text-xs text-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-planner" />
            {statusMessage}
          </div>
        ) : null}
        <div ref={bottomRef} className="h-1" />
      </div>
    </div>
  );
}
