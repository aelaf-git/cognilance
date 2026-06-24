import { AgentSidebar } from "@/components/AgentSidebar";
import { ChatComposer } from "@/components/ChatComposer";
import { OrchestrationFeed } from "@/components/OrchestrationFeed";
import { useChatStream } from "@/hooks/useChatStream";

export default function App() {
  const { turns, send, isStreaming, statusMessage, hiredAgents } = useChatStream();

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-center gap-4 border-b border-border bg-background px-5 py-4">
        <img src="/logo.png" alt="Cognilance" className="h-7 w-auto object-contain" />
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Orchestrator
          </p>
          <p className="text-xs text-dim">Planner · routing · generative UI</p>
        </div>
        {isStreaming ? (
          <span className="ml-auto flex items-center gap-2 text-xs text-planner">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-planner" />
            Live
          </span>
        ) : null}
      </header>

      <div className="flex min-h-0 flex-1">
        <AgentSidebar agents={hiredAgents} isStreaming={isStreaming} />
        <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-background">
          <OrchestrationFeed turns={turns} statusMessage={statusMessage} />
          <ChatComposer onSend={send} disabled={isStreaming} />
        </main>
      </div>
    </div>
  );
}
