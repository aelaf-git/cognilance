import { useCallback, useEffect, useRef, useState } from "react";
import { ChatComposer } from "@/components/ChatComposer";
import { ChatFeed } from "@/components/ChatFeed";
import {
  ConversationSidebar,
  ConversationSidebarCollapsed,
} from "@/components/ConversationSidebar";
import { MarketplaceAgentsModal } from "@/components/MarketplaceAgentsModal";
import { WalletBar } from "@/components/WalletBar";
import {
  SessionDetailCollapsed,
  SessionDetailModal,
  SessionListPanel,
} from "@/components/SessionDetailPanel";
import { ResizeHandle } from "@/components/ResizeHandle";
import { useConversations } from "@/hooks/useConversations";
import { useMediaQuery } from "@/hooks/useMediaQuery";
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
  const [marketplaceOpen, setMarketplaceOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const isMobile = useMediaQuery("(max-width: 767px)");
  const wasMobileRef = useRef(isMobile);

  const {
    conversations,
    activeConversationId,
    setActiveConversationId,
    conversationSessions,
    refresh: refreshConversations,
    selectConversation: selectConversationMeta,
    deleteConversation,
    loadConversationSessions,
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
    stop,
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

  // Collapse panels only when the viewport crosses into mobile.
  useEffect(() => {
    if (isMobile && !wasMobileRef.current) {
      if (sidebarExpanded) toggleSidebar();
      if (detailExpanded) toggleDetail();
    }
    wasMobileRef.current = isMobile;
  }, [isMobile, sidebarExpanded, detailExpanded, toggleSidebar, toggleDetail]);

  const handleSelectConversation = useCallback(
    async (conversationId: string) => {
      setModalSessionId(null);
      const ok = await selectConversation(conversationId);
      if (!ok) {
        setActiveConversationId(null);
        localStorage.removeItem(CONVERSATION_KEY);
        return;
      }
      setActiveConversationId(conversationId);
      localStorage.setItem(CONVERSATION_KEY, conversationId);
      await selectConversationMeta(conversationId);
      if (isMobile && sidebarExpanded) toggleSidebar();
    },
    [
      isMobile,
      selectConversation,
      selectConversationMeta,
      setActiveConversationId,
      sidebarExpanded,
      toggleSidebar,
    ],
  );

  const handleNewChat = useCallback(async () => {
    setModalSessionId(null);
    const id = await newChat();
    setActiveConversationId(id);
    await refreshConversations();
    await loadConversationSessions(id);
    if (isMobile && sidebarExpanded) toggleSidebar();
  }, [
    isMobile,
    loadConversationSessions,
    newChat,
    refreshConversations,
    setActiveConversationId,
    sidebarExpanded,
    toggleSidebar,
  ]);

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
    const activeStillValid =
      !!activeConversationId && conversations.some((c) => c.id === activeConversationId);
    if (activeStillValid) return;

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
    let cancelled = false;

    const tick = async () => {
      const result = await loadConversationSessions(activeConversationId);
      if (cancelled || result !== null) return;
      setActiveConversationId(null);
      localStorage.removeItem(CONVERSATION_KEY);
    };

    void tick();
    const interval = window.setInterval(() => void tick(), 4000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [activeConversationId, loadConversationSessions, setActiveConversationId]);

  const handleOpenSession = (sessionId: string) => {
    const session = conversationSessions.find((s) => s.id === sessionId);
    setModalSessionId(sessionId);
    if (!sessionTurns[sessionId]) {
      void loadSessionHistory(sessionId);
    }
    if (session?.status === "running" || session?.status === "queued") {
      void watchLiveSession(sessionId);
    }
    if (isMobile && detailExpanded) toggleDetail();
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
    await stop(sessionId);
    if (modalSessionId === sessionId) {
      void loadSessionHistory(sessionId);
    }
    if (activeConversationId) {
      await loadConversationSessions(activeConversationId);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="shrink-0 border-b border-border bg-background px-3 py-3 sm:px-5 sm:py-4">
        <div className="flex flex-wrap items-center gap-2 sm:gap-4">
          <img
            src="/logo.png"
            alt="Cognilance"
            className="h-6 w-auto object-contain sm:h-7"
          />
          <div className="min-w-0 flex-1 sm:flex-none">
            <p className="truncate text-[10px] font-semibold uppercase tracking-[0.14em] text-muted sm:text-[11px]">
              Orchestrator Agent
            </p>
          </div>

          {isStreaming ? (
            <span className="flex items-center gap-2 text-xs text-planner">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-planner" />
              Live
            </span>
          ) : null}

          <button
            type="button"
            className="ml-auto rounded-md border border-border px-2.5 py-1.5 text-xs text-muted hover:text-white md:hidden"
            onClick={() => setNavOpen((v) => !v)}
            aria-expanded={navOpen}
          >
            {navOpen ? "Close" : "Menu"}
          </button>

          <nav
            className={`${
              navOpen ? "flex" : "hidden"
            } w-full flex-col gap-3 border-t border-border pt-3 md:ml-auto md:flex md:w-auto md:flex-row md:flex-wrap md:items-center md:gap-4 md:border-0 md:pt-0`}
          >
            <WalletBar compact={isMobile} />
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  setMarketplaceOpen(true);
                  setNavOpen(false);
                }}
                className="text-xs text-registry hover:underline"
              >
                Marketplace
              </button>
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
          </nav>
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {/* Conversations — desktop rail / mobile drawer */}
        {sidebarExpanded ? (
          <>
            {isMobile ? (
              <button
                type="button"
                className="fixed inset-0 z-40 bg-black/60"
                aria-label="Close conversations"
                onClick={toggleSidebar}
              />
            ) : null}
            <div
              className={
                isMobile
                  ? "fixed inset-y-0 left-0 z-50 flex w-[min(100vw,20rem)] max-w-[85vw] flex-col overflow-hidden border-r border-border bg-background shadow-2xl"
                  : "flex h-full shrink-0 flex-col overflow-hidden border-r border-border"
              }
              style={isMobile ? undefined : { width: sidebarWidth }}
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
            {!isMobile ? (
              <ResizeHandle
                getWidth={getSidebarWidth}
                setWidth={resizeSidebar}
                min={MIN_SIDEBAR_W}
                max={MAX_SIDEBAR_W}
                onResizeEnd={persistSidebarWidth}
              />
            ) : null}
          </>
        ) : (
          <ConversationSidebarCollapsed onExpand={toggleSidebar} />
        )}

        <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-background">
          <ChatFeed messages={chatMessages} isStreaming={isStreaming} />
          <ChatComposer
            onSend={(text) => void handleSend(text)}
            onStop={() => void stop()}
            disabled={conversationLoading}
            isStreaming={isStreaming}
          />
        </main>

        {/* Sessions — desktop rail / mobile drawer */}
        {detailExpanded ? (
          <>
            {isMobile ? (
              <button
                type="button"
                className="fixed inset-0 z-40 bg-black/60"
                aria-label="Close sessions"
                onClick={toggleDetail}
              />
            ) : null}
            {!isMobile ? (
              <ResizeHandle
                invert
                getWidth={getDetailWidth}
                setWidth={resizeDetail}
                min={MIN_DETAIL_W}
                max={MAX_DETAIL_W}
                onResizeEnd={persistDetailWidth}
              />
            ) : null}
            <div
              className={
                isMobile
                  ? "fixed inset-y-0 right-0 z-50 flex w-[min(100vw,22rem)] max-w-[90vw] flex-col overflow-hidden border-l border-border bg-background shadow-2xl"
                  : "flex h-full shrink-0 flex-col overflow-hidden border-l border-border"
              }
              style={isMobile ? undefined : { width: detailWidth }}
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

      {marketplaceOpen ? (
        <MarketplaceAgentsModal onClose={() => setMarketplaceOpen(false)} />
      ) : null}
    </div>
  );
}
