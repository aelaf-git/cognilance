import { useCallback, useEffect, useState } from "react";
import { ChatComposer } from "@/components/ChatComposer";
import { ChatFeed } from "@/components/ChatFeed";
import {
  ConversationSidebar,
  ConversationSidebarCollapsed,
} from "@/components/ConversationSidebar";
import {
  SessionDetailCollapsed,
  SessionDetailModal,
  SessionListPanel,
} from "@/components/SessionDetailPanel";
import { ResizeHandle } from "@/components/ResizeHandle";
import { useConversations } from "@/hooks/useConversations";
import { useOrchestrator } from "@/hooks/useOrchestrator";
import {
  usePanelLayout,
  MIN_DETAIL_W,
  MAX_DETAIL_W,
  MIN_SIDEBAR_W,
  MAX_SIDEBAR_W,
} from "@/hooks/usePanelLayout";

const CONVERSATION_KEY = "cognilance_orchestrator_conversation";

export default function App() {
  const [modalSessionId, setModalSessionId] = useState<string | null>(null);

  const {
    conversations,
    activeConversationId,
    setActiveConversationId,
    conversationSessions,
    refresh: refreshConversations,
    selectConversation: selectConversationMeta,
    deleteConversation,
    loadConversationSessions,
    abortSession,
  } = useConversations();

  const {
    sidebarExpanded,
    detailExpanded,
    sidebarWidth,
    detailWidth,
    toggleSidebar,
    toggleDetail,
    resizeSidebar,
    resizeDetail,
    getSidebarWidth,
    getDetailWidth,
    persistSidebarWidth,
    persistDetailWidth,
  } = usePanelLayout();

  const {
    chatMessages,
    sessionTurns,
    send,
    loadSessionHistory,
    watchLiveSession,
    isStreaming,
    conversationLoading,
    conversationId,
    newChat,
    selectConversation,
  } = useOrchestrator(refreshConversations);

  const modalSession = modalSessionId
    ? (conversationSessions.find((s) => s.id === modalSessionId) ?? null)
    : null;
  const modalTurn = modalSessionId ? sessionTurns[modalSessionId] ?? null : null;

  const handleSelectConversation = useCallback(
    async (conversationId: string) => {
      setModalSessionId(null);
      setActiveConversationId(conversationId);
      localStorage.setItem(CONVERSATION_KEY, conversationId);
      await selectConversation(conversationId);
      await selectConversationMeta(conversationId);
    },
    [selectConversation, selectConversationMeta, setActiveConversationId],
  );

  const handleNewChat = useCallback(async () => {
    setModalSessionId(null);
    const id = await newChat();
    setActiveConversationId(id);
    await refreshConversations();
    await loadConversationSessions(id);
  }, [loadConversationSessions, newChat, refreshConversations, setActiveConversationId]);

  const handleDeleteConversation = useCallback(
    async (conversationId: string) => {
      const deleted = await deleteConversation(conversationId);
      if (!deleted) return;
      setModalSessionId(null);
      if (activeConversationId !== conversationId) return;
      const remaining = conversations.filter((c) => c.id !== conversationId);
      if (remaining.length > 0) {
        await handleSelectConversation(remaining[0].id);
      } else {
        await handleNewChat();
      }
    },
    [
      activeConversationId,
      conversations,
      deleteConversation,
      handleNewChat,
      handleSelectConversation,
    ],
  );

  useEffect(() => {
    if (conversationLoading) return;
    if (conversations.length === 0) {
      if (!activeConversationId) void handleNewChat();
      return;
    }
    if (activeConversationId) return;
    const saved = localStorage.getItem(CONVERSATION_KEY);
    const match = saved ? conversations.find((c) => c.id === saved) : null;
    void handleSelectConversation(match?.id ?? conversations[0].id);
  }, [
    activeConversationId,
    conversationLoading,
    conversations,
    handleNewChat,
    handleSelectConversation,
  ]);

  useEffect(() => {
    if (!activeConversationId) return;
    void loadConversationSessions(activeConversationId);
    const interval = window.setInterval(() => {
      void loadConversationSessions(activeConversationId);
    }, 4000);
    return () => window.clearInterval(interval);
  }, [activeConversationId, loadConversationSessions]);

  const handleOpenSession = (sessionId: string) => {
    const session = conversationSessions.find((s) => s.id === sessionId);
    setModalSessionId(sessionId);
    if (!sessionTurns[sessionId]) {
      void loadSessionHistory(sessionId);
    }
    if (session?.status === "running" || session?.status === "queued") {
      void watchLiveSession(sessionId);
    }
  };

  const handleSend = async (text: string) => {
    const sessionId = await send(text);
    const convId = conversationId;
    if (convId) {
      if (convId !== activeConversationId) {
        setActiveConversationId(convId);
      }
      await loadConversationSessions(convId);
    }
    await refreshConversations();
    if (sessionId && !sessionTurns[sessionId]) {
      void loadSessionHistory(sessionId);
    }
  };

  const handleAbortSession = async (sessionId: string) => {
    await abortSession(sessionId);
    if (modalSessionId === sessionId) {
      void loadSessionHistory(sessionId);
    }
    if (activeConversationId) {
      await loadConversationSessions(activeConversationId);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-center gap-4 border-b border-border bg-background px-5 py-4">
        <img src="/logo.png" alt="Cognilance" className="h-7 w-auto object-contain" />
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted">
            Orchestrator Agent
          </p>
        </div>
        <div className="ml-auto flex items-center gap-4">
          {isStreaming ? (
            <span className="flex items-center gap-2 text-xs text-planner">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-planner" />
              Live
            </span>
          ) : null}
          <a href="/integrations" className="text-xs text-registry hover:underline">
            Integrations
          </a>
          <a
            href="http://127.0.0.1:8300"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-registry hover:underline"
          >
            Developer portal
          </a>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {sidebarExpanded ? (
          <>
            <div
              className="flex h-full shrink-0 flex-col overflow-hidden border-r border-border"
              style={{ width: sidebarWidth }}
            >
              <ConversationSidebar
                conversations={conversations}
                activeConversationId={activeConversationId}
                onCollapse={toggleSidebar}
                onSelect={(id) => void handleSelectConversation(id)}
                onDelete={(id) => void handleDeleteConversation(id)}
                onNewChat={() => void handleNewChat()}
                newChatDisabled={isStreaming || conversationLoading}
              />
            </div>
            <ResizeHandle
              getWidth={getSidebarWidth}
              setWidth={resizeSidebar}
              min={MIN_SIDEBAR_W}
              max={MAX_SIDEBAR_W}
              onResizeEnd={persistSidebarWidth}
            />
          </>
        ) : (
          <ConversationSidebarCollapsed onExpand={toggleSidebar} />
        )}

        <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-background">
          <ChatFeed messages={chatMessages} isStreaming={isStreaming} />
          <ChatComposer
            onSend={(text) => void handleSend(text)}
            disabled={isStreaming || conversationLoading}
          />
        </main>

        {detailExpanded ? (
          <>
            <ResizeHandle
              invert
              getWidth={getDetailWidth}
              setWidth={resizeDetail}
              min={MIN_DETAIL_W}
              max={MAX_DETAIL_W}
              onResizeEnd={persistDetailWidth}
            />
            <div
              className="flex h-full shrink-0 flex-col overflow-hidden border-l border-border"
              style={{ width: detailWidth }}
            >
              <SessionListPanel
                sessions={conversationSessions}
                onSelectSession={handleOpenSession}
                onAbortSession={(id) => void handleAbortSession(id)}
                onCollapse={toggleDetail}
              />
            </div>
          </>
        ) : (
          <SessionDetailCollapsed onExpand={toggleDetail} />
        )}
      </div>

      {modalSession ? (
        <SessionDetailModal
          session={modalSession}
          turn={modalTurn}
          onClose={() => setModalSessionId(null)}
          onAbort={(id) => void handleAbortSession(id)}
        />
      ) : null}
    </div>
  );
}
