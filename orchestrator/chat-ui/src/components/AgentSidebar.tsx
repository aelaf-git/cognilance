import { motion } from "framer-motion";
import { Bot, Circle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { HiredAgent } from "@/types";

function statusIcon(status: HiredAgent["runStatus"]) {
  if (status === "executing") return <Loader2 className="h-3.5 w-3.5 animate-spin text-registry" />;
  if (status === "done") return <Circle className="h-3 w-3 fill-genui text-genui" />;
  return <Circle className="h-3 w-3 text-dim" />;
}

export function AgentSidebar({
  agents,
  isStreaming,
}: {
  agents: HiredAgent[];
  isStreaming: boolean;
}) {
  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-background">
      <div className="border-b border-border px-4 py-4">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-registry" />
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
            Hired Agents
          </h2>
        </div>
        <p className="mt-1 text-[11px] text-dim">Specialists engaged this run</p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 scrollbar-thin">
        {agents.length === 0 ? (
          <p className="rounded-lg border border-border bg-surface p-3 text-xs leading-relaxed text-muted">
            {isStreaming
              ? "Waiting for the orchestrator to hire specialists…"
              : "No marketplace agents were hired. Simple prompts are answered directly by the thinking agent."}
          </p>
        ) : (
          <TooltipProvider delayDuration={200}>
            <div className="space-y-2">
              {agents.map((agent, i) => (
                <motion.div
                  key={agent.name}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                >
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Card className="border-l-[3px] border-l-registry bg-surface transition-colors hover:border-border">
                        <CardHeader className="space-y-0 p-3 pb-1">
                          <div className="flex items-start justify-between gap-2">
                            <CardTitle className="text-sm font-medium leading-tight">
                              {agent.name}
                            </CardTitle>
                            {statusIcon(agent.runStatus)}
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-2 p-3 pt-1">
                          {agent.skill ? (
                            <span className="inline-block rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] text-registry">
                              {agent.skill}
                            </span>
                          ) : null}
                          <Badge variant={agent.runStatus}>{agent.runStatus}</Badge>
                        </CardContent>
                      </Card>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="max-w-xs">
                      <p className="font-medium">{agent.name}</p>
                      {agent.skill ? (
                        <p className="mt-1 font-mono text-xs text-muted">{agent.skill}</p>
                      ) : null}
                    </TooltipContent>
                  </Tooltip>
                </motion.div>
              ))}
            </div>
          </TooltipProvider>
        )}
      </div>
    </aside>
  );
}
