import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapsibleSection } from "@/components/ui/collapsible";
import { GenUiRenderer } from "@/components/GenUiRenderer";
import { cn } from "@/lib/utils";
import type { FeedCard, StepStatus, SubtaskItem } from "@/types";
import { CARD_META } from "@/types";

function StatusBadge({ status }: { status: StepStatus }) {
  return <Badge variant={status}>{status}</Badge>;
}

function SubtaskList({ subtasks }: { subtasks: SubtaskItem[] }) {
  if (!subtasks.length) return null;
  return (
    <div className="space-y-2">
      {subtasks.map((st) => (
        <div
          key={st.id}
          className="flex items-start gap-3 rounded-md border border-border/80 bg-background/60 p-3"
        >
          <StatusBadge status={st.status} />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-white">
              {st.title}
              {st.assignee ? (
                <span className="ml-1.5 font-normal text-registry">· {st.assignee}</span>
              ) : null}
            </div>
            {(st.instruction || st.detail) && (
              <p className="mt-1 font-mono text-xs leading-relaxed text-muted">
                {st.instruction || st.detail}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function FeedCardView({ card, index }: { card: FeedCard; index: number }) {
  const meta = CARD_META[card.type];
  const hasBody =
    card.content ||
    card.subtasks?.length ||
    card.uiComponent ||
    card.route;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1], delay: index * 0.04 }}
    >
      <Card className={cn("border-l-[3px] bg-surface", meta.accentClass)}>
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
          <div className="flex items-center gap-2.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: meta.accent }}
            />
            <CardTitle className="text-[13px] font-medium text-white/95">
              {meta.label}
            </CardTitle>
          </div>
          <StatusBadge status={card.status} />
        </CardHeader>
        {hasBody ? (
          <CardContent className="space-y-3">
            {card.type === "routing" && card.route ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md border border-border bg-background px-2.5 py-1 text-xs font-medium uppercase tracking-wide text-white">
                  {card.route}
                </span>
                {card.complexity ? (
                  <span className="text-xs text-muted">complexity: {card.complexity}</span>
                ) : null}
              </div>
            ) : null}

            {card.content ? (
              <CollapsibleSection
                title={card.mono ? "Raw output" : "Details"}
                defaultOpen={card.type !== "planner"}
              >
                <pre
                  className={cn(
                    "max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-background/80 p-3 text-sm leading-relaxed text-white/90 scrollbar-thin",
                    card.mono ? "font-mono text-xs text-muted" : "",
                  )}
                >
                  {card.content}
                </pre>
              </CollapsibleSection>
            ) : null}

            {card.subtasks?.length ? <SubtaskList subtasks={card.subtasks} /> : null}

            {card.type === "gen-ui" ? (
              card.uiComponent ? (
                <div>
                  <p className="mb-3 text-xs uppercase tracking-wider text-genui">
                    Component: {card.uiComponent}
                  </p>
                  <GenUiRenderer
                    item={{ name: card.uiComponent, props: card.uiProps ?? {} }}
                  />
                </div>
              ) : (
                <p className="text-sm text-muted">Plain text response — no rich UI selected.</p>
              )
            ) : null}
          </CardContent>
        ) : card.status === "running" ? (
          <CardContent>
            <div className="flex items-center gap-2 text-sm text-muted">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-planner" />
              In progress…
            </div>
          </CardContent>
        ) : null}
      </Card>
    </motion.div>
  );
}
