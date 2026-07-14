import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapsibleSection } from "@/components/ui/collapsible";
import { GenUiRenderer } from "@/components/GenUiRenderer";
import { cn } from "@/lib/utils";
import type { CatalogAgent, FeedCard, StepStatus, SubtaskItem } from "@/types";
import { CARD_META } from "@/types";

function StatusBadge({ status }: { status: StepStatus }) {
  return <Badge variant={status}>{status}</Badge>;
}

function roleLabel(st: SubtaskItem): { kind: string; label: string; className: string } {
  const tool = st.tool || st.toolLabel || "";
  if (tool.startsWith("hire:") || st.skill) {
    return {
      kind: "hired",
      label: `Hired · ${st.assignee || st.skill || tool.slice(5)}`,
      className: "border-registry/40 bg-registry/10 text-registry",
    };
  }
  if (tool.startsWith("app:")) {
    return {
      kind: "app",
      label: `App · ${st.assignee || tool.slice(4)}`,
      className: "border-task/40 bg-task/10 text-task",
    };
  }
  if (tool.startsWith("web")) {
    return {
      kind: "web",
      label: "Web",
      className: "border-planner/40 bg-planner/10 text-planner",
    };
  }
  if (st.assignee === "thinking" || tool === "thinking") {
    return {
      kind: "thinking",
      label: "Thinking agent",
      className: "border-thinking/40 bg-thinking/10 text-thinking",
    };
  }
  return {
    kind: "agent",
    label: st.assignee || "Agent",
    className: "border-border bg-surface text-muted",
  };
}

function statusDot(status: StepStatus): string {
  if (status === "running") return "bg-planner animate-pulse";
  if (status === "done") return "bg-registry";
  if (status === "fallback") return "bg-thinking";
  return "bg-dim";
}

function SubtaskList({ subtasks }: { subtasks: SubtaskItem[] }) {
  if (!subtasks.length) return null;
  return (
    <div className="relative space-y-0">
      <div className="absolute bottom-3 left-[15px] top-3 w-px bg-border/80" aria-hidden />
      {subtasks.map((st, index) => {
        const role = roleLabel(st);
        const brief = st.instruction || st.detail;
        return (
          <motion.div
            key={st.id}
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05, duration: 0.3 }}
            className="relative flex gap-3 pb-4 last:pb-0"
          >
            <div className="relative z-10 mt-3 flex h-[11px] w-[11px] shrink-0 items-center justify-center rounded-full border border-border bg-background">
              <span className={cn("h-2 w-2 rounded-full", statusDot(st.status))} />
            </div>
            <div className="min-w-0 flex-1 rounded-lg border border-border/80 bg-background/70 p-3.5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0 space-y-1.5">
                  <p className="text-sm font-medium text-white">{st.title}</p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium",
                        role.className,
                      )}
                    >
                      {role.label}
                    </span>
                    {st.skill ? (
                      <span className="rounded-md border border-border px-2 py-0.5 font-mono text-[10px] text-dim">
                        skill:{st.skill}
                      </span>
                    ) : null}
                    {st.tool && !st.tool.startsWith("hire:") ? (
                      <span className="rounded-md border border-border px-2 py-0.5 font-mono text-[10px] text-dim">
                        {st.tool}
                      </span>
                    ) : null}
                  </div>
                </div>
                <StatusBadge status={st.status} />
              </div>

              {brief ? (
                <div className="mt-3 rounded-md border border-border/60 bg-surface/50 px-3 py-2">
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-dim">
                    Task brief
                  </p>
                  <p className="text-xs leading-relaxed text-muted">{brief}</p>
                </div>
              ) : null}

              {st.result ? (
                <CollapsibleSection title="Result" defaultOpen={false} className="mt-3">
                  <p className="max-h-40 overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-white/85 scrollbar-thin">
                    {st.result}
                  </p>
                </CollapsibleSection>
              ) : null}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

function ThinkingPanel({
  thinking,
  running,
}: {
  thinking: string;
  running?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-planner/25 bg-planner/[0.06]">
      <div className="flex items-center gap-2 border-b border-planner/20 px-3 py-2">
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full bg-planner",
            running && "animate-pulse",
          )}
        />
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-planner">
          Thinking process
        </p>
        {running ? <span className="text-[10px] text-dim">live</span> : null}
      </div>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap p-3 font-sans text-[13px] leading-relaxed text-white/90 scrollbar-thin">
        {thinking}
      </pre>
    </div>
  );
}

function PlanPanel({ content }: { content: string }) {
  return (
    <CollapsibleSection title="Execution plan" defaultOpen>
      <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-md border border-border/70 bg-background/80 p-3 text-sm leading-relaxed text-white/90 scrollbar-thin">
        {content}
      </pre>
    </CollapsibleSection>
  );
}

function CatalogPanel({ agents }: { agents: CatalogAgent[] }) {
  if (!agents.length) {
    return (
      <p className="rounded-md border border-border/70 bg-background/80 px-3 py-2 text-xs text-muted">
        No agents returned from the registry.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {agents.map((agent) => {
        const chatUrl = agent.url
          ? `${String(agent.url).replace(/\/$/, "")}/chat`
          : null;
        return (
          <div
            key={`${agent.name}-${agent.url ?? ""}`}
            className="rounded-lg border border-registry/30 bg-registry/[0.06] px-3 py-2.5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-white">{agent.name}</p>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={cn(
                    "rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                    agent.online
                      ? "border-registry/40 bg-registry/15 text-registry"
                      : "border-border text-dim",
                  )}
                >
                  {agent.online ? "online" : "offline"}
                </span>
                {chatUrl && agent.online ? (
                  <a
                    href={chatUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-md border border-registry/40 bg-registry/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-registry transition-colors hover:bg-registry/25"
                  >
                    Chat with agent
                  </a>
                ) : null}
              </div>
            </div>
            {agent.skills.length ? (
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
        );
      })}
    </div>
  );
}

export function FeedCardView({ card, index }: { card: FeedCard; index: number }) {
  const meta = CARD_META[card.type];
  const hasBody =
    card.content ||
    card.thinking ||
    card.subtasks?.length ||
    card.catalogAgents?.length ||
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
            {card.type === "registry" ? (
              <>
                {card.content ? (
                  <p className="text-xs leading-relaxed text-muted">{card.content}</p>
                ) : null}
                <CatalogPanel agents={card.catalogAgents ?? []} />
              </>
            ) : null}

            {card.type === "routing" && card.route ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md border border-thinking/30 bg-thinking/10 px-2.5 py-1 text-xs font-medium uppercase tracking-wide text-thinking">
                  {card.route}
                </span>
                {card.complexity ? (
                  <span className="text-xs text-muted">complexity: {card.complexity}</span>
                ) : null}
              </div>
            ) : null}

            {card.type === "planner" && card.thinking ? (
              <ThinkingPanel thinking={card.thinking} running={card.status === "running"} />
            ) : null}

            {card.type === "planner" && card.content ? <PlanPanel content={card.content} /> : null}

            {card.type !== "planner" && card.type !== "registry" && card.content ? (
              <CollapsibleSection
                title={card.mono ? "Raw output" : "Details"}
                defaultOpen={card.type === "delegation" || card.type === "routing"}
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
