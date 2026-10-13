import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, OrchestrationTurn, UiItem } from "@/types";
import {
  applySessionEvent,
  createEventContext,
  extractChatOutput,
  extractUiItem,
  finalizeSessionTurn,
  isOutputEvent,
  makeCard,
} from "@/lib/sessionEvents";

const CONVERSATION_KEY = "cognilance_orchestrator_conversation";

function uid() {
  return crypto.randomUUID();
}

function emptySessionTurn(sessionId: string): OrchestrationTurn {
  return {
    id: uid(),
    sessionId,
    cards: [makeCard("planner", { status: "running", content: "" })],
  };
}

type ConversationMessage = {
  id: number;
  role: string;
  content: string;
  ui?: UiItem | null;
};

export function useOrchestrator(
  onSessionUpdate?: () => void,
  onSessionStarted?: (sessionId: string) => void,
  onActiveDocEvent?: (data: Record<string, unknown>) => void,
) {
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [sessionTurns, setSessionTurns] = useState<Record<string, OrchestrationTurn>>({});
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState(
    () => localStorage.getItem(CONVERSATION_KEY) ?? "",
  );
  const [conversationLoading, setConversationLoading] = useState(true);
  const conversationIdRef = useRef(conversationId);
  const liveSessionRef = useRef<string | null>(null);
  const lastNotificationIdRef = useRef(0);
  const notificationAbortRef = useRef<AbortController | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const liveAssistantIdRef = useRef<string | null>(null);

  useEffect(() => {
    conversationIdRef.current = conversationId;
    if (conversationId) {
      localStorage.setItem(CONVERSATION_KEY, conversationId);
    }
    lastNotificationIdRef.current = 0;
  }, [conversationId]);

  useEffect(() => {
    if (!conversationId) return;
    const controller = new AbortController();
    notificationAbortRef.current = controller;
    const watchingId = conversationId;

    async function watchNotifications() {
      try {
        const res = await fetch(
          `/conversations/${watchingId}/notifications?after=${lastNotificationIdRef.current}`,
          { signal: controller.signal },
        );
        if (res.status === 404) {
          if (conversationIdRef.current === watchingId) {
            conversationIdRef.current = "";
            setConversationId("");
            localStorage.removeItem(CONVERSATION_KEY);
          }
          return;
        }
        if (!res.ok || !res.body) return;
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!controller.signal.aborted) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";
          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6)) as {
                id?: number;
                summary?: string;
                event?: string;
              };
              if (data.id) lastNotificationIdRef.current = Math.max(lastNotificationIdRef.current, data.id);
              const summary = data.summary?.trim();
              if (!summary) continue;
              setChatMessages((prev) => {
                if (prev.some((m) => m.content === summary && m.role === "assistant")) {
                  return prev;
                }
                return [
                  ...prev,
                  {
                    id: `notif-${data.id ?? uid()}`,
                    role: "assistant",
                    content: summary,
                  },
                ];
              });
            } catch {
              continue;
            }
          }
        }
      } catch {
        /* aborted or network */
      }
    }

    void watchNotifications();
    return () => {
      controller.abort();
      notificationAbortRef.current = null;
    };
  }, [conversationId]);

  const loadConversation = useCallback(async (id: string) => {
    try {
      const res = await fetch(`/conversations/${id}`);
      if (!res.ok) return false;
      const data = await res.json();
      const messages = (data.messages ?? []) as ConversationMessage[];
      setChatMessages(
        messages.map((m) => ({
          id: `msg-${m.id}`,
          role: m.role === "user" ? "user" : "assistant",
          content: m.content,
          ui: m.ui ?? null,
        })),
      );
      return true;
    } catch {
      return false;
    }
  }, []);

  const selectConversation = useCallback(
    async (id: string) => {
      const ok = await loadConversation(id);
      if (!ok) {
        conversationIdRef.current = "";
        setConversationId("");
        localStorage.removeItem(CONVERSATION_KEY);
        setChatMessages([]);
        setSessionTurns({});
        return false;
      }
      conversationIdRef.current = id;
      setConversationId(id);
      localStorage.setItem(CONVERSATION_KEY, id);
      setSessionTurns({});
      return true;
    },
    [loadConversation],
  );

  const newChat = useCallback(async () => {
    const res = await fetch("/conversations", { method: "POST" });
    if (!res.ok) throw new Error("Failed to create conversation");
    const data = await res.json();
    const id = String(data.id);
    conversationIdRef.current = id;
    setConversationId(id);
    localStorage.setItem(CONVERSATION_KEY, id);
    setChatMessages([]);
    setSessionTurns({});
    return id;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setConversationLoading(true);
      try {
        const existing = conversationIdRef.current;
        if (existing) {
          const ok = await loadConversation(existing);
          if (!ok && !cancelled) {
            conversationIdRef.current = "";
            setConversationId("");
            localStorage.removeItem(CONVERSATION_KEY);
          }
        }
      } finally {
        if (!cancelled) setConversationLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadConversation]);

  const onActiveDocEventRef = useRef(onActiveDocEvent);
  onActiveDocEventRef.current = onActiveDocEvent;

  const processEvent = useCallback(
    (
      sessionId: string,
      data: Record<string, unknown>,
      assistantId: string | null,
      ctx: ReturnType<typeof createEventContext>,
    ) => {
      const event = data.event as string;

      if (
        (event === "subtask_start" ||
          event === "subtask_done" ||
          event === "final" ||
          event === "plan") &&
        (data.document_id ||
          data.document_url ||
          data.skill ||
          data.tool ||
          data.subtasks ||
          data.data ||
          data.text)
      ) {
        onActiveDocEventRef.current?.(data);
      }

      setSessionTurns((prev) => {
        const turn = prev[sessionId] ?? emptySessionTurn(sessionId);
        const updated = applySessionEvent(turn, data, ctx);
        return { ...prev, [sessionId]: { ...updated, sessionId } };
      });

      if (assistantId && isOutputEvent(event)) {
        setChatMessages((prev) =>
          prev.map((m) => {
            if (m.id !== assistantId) return m;
            const content = extractChatOutput(m.content, data, ctx);
            return {
              ...m,
              content,
              ui: extractUiItem(data) ?? m.ui,
              streaming:
                event !== "final" &&
                event !== "answer_done" &&
                event !== "error" &&
                event !== "session_aborted",
              error: event === "error",
            };
          }),
        );
      } else if (assistantId) {
        const uiItem = extractUiItem(data);
        if (uiItem) {
          setChatMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, ui: uiItem } : m)),
          );
        }
      }
    },
    [],
  );

  const processStream = useCallback(
    async (
      body: ReadableStream<Uint8Array>,
      sessionId: string,
      assistantId: string | null,
      signal?: AbortSignal,
    ) => {
      const ctx = createEventContext();
      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const onAbort = () => {
        void reader.cancel();
      };
      if (signal) {
        if (signal.aborted) {
          void reader.cancel();
          return;
        }
        signal.addEventListener("abort", onAbort, { once: true });
      }

      try {
        while (true) {
          if (signal?.aborted) break;
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith("data: ")) continue;
            let data: Record<string, unknown>;
            try {
              data = JSON.parse(line.slice(6));
            } catch {
              continue;
            }

            if (data.event === "session_created" || data.event === "mission_created") {
              liveSessionRef.current = String(data.session_id ?? data.mission_id);
            }
            if (data.conversation_id) {
              const cid = String(data.conversation_id);
              conversationIdRef.current = cid;
              setConversationId(cid);
            } else if (data.thread_id) {
              const cid = String(data.thread_id);
              conversationIdRef.current = cid;
              setConversationId(cid);
            }

            processEvent(sessionId, data, assistantId, ctx);
          }
        }
      } finally {
        signal?.removeEventListener("abort", onAbort);
      }

      setSessionTurns((prev) => {
        const turn = prev[sessionId];
        if (!turn) return prev;
        return { ...prev, [sessionId]: finalizeSessionTurn(turn, ctx) };
      });

      if (assistantId) {
        const lastUi =
          [...ctx.uiItems].reverse().find((item) => item.name !== "text-card") ?? null;
        setChatMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: m.content || ctx.answer,
                  ui: m.ui ?? lastUi,
                  streaming: false,
                }
              : m,
          ),
        );
      }
    },
    [processEvent],
  );

  const stop = useCallback(async (sessionId?: string) => {
    const liveId = liveSessionRef.current;
    const target = sessionId ?? liveId;
    const isLiveTarget = Boolean(liveId && (!sessionId || sessionId === liveId));
    if (isLiveTarget) {
      streamAbortRef.current?.abort();
      streamAbortRef.current = null;
    }
    if (target) {
      try {
        await fetch(`/sessions/${target}/abort`, { method: "POST" });
      } catch {
        /* ignore network errors — local abort still stops the UI stream */
      }
    }
    if (isLiveTarget) {
      setIsStreaming(false);
      const assistantId = liveAssistantIdRef.current;
      if (assistantId) {
        setChatMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: m.content.trim() || "Stopped.",
                  streaming: false,
                }
              : m,
          ),
        );
      }
      liveAssistantIdRef.current = null;
    }
    onSessionUpdate?.();
  }, [onSessionUpdate]);

  const send = useCallback(
    async (text: string) => {
      let convId = conversationIdRef.current;
      if (!convId) {
        convId = await newChat();
      }
      const userId = uid();
      const assistantId = uid();
      liveAssistantIdRef.current = assistantId;
      setChatMessages((prev) => [
        ...prev,
        { id: userId, role: "user", content: text },
        { id: assistantId, role: "assistant", content: "", streaming: true },
      ]);
      setIsStreaming(true);
      liveSessionRef.current = null;
      const controller = new AbortController();
      streamAbortRef.current = controller;

      let sessionId = "";

      try {
        const res = await fetch("/chat/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text,
            conversation_id: convId,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          }),
          signal: controller.signal,
        });
        if (!res.ok || !res.body) throw new Error("Stream request failed");
        sessionId =
          res.headers.get("X-Session-Id") ??
          res.headers.get("X-Mission-Id") ??
          liveSessionRef.current ??
          uid();
        liveSessionRef.current = sessionId;
        setSessionTurns((prev) => ({
          ...prev,
          [sessionId]: prev[sessionId] ?? emptySessionTurn(sessionId),
        }));
        onSessionStarted?.(sessionId);
        await processStream(res.body, sessionId, assistantId, controller.signal);
      } catch (err) {
        if (controller.signal.aborted) {
          setChatMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: m.content.trim() || "Stopped.",
                    streaming: false,
                  }
                : m,
            ),
          );
        } else {
          setChatMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: err instanceof Error ? err.message : String(err),
                    streaming: false,
                    error: true,
                  }
                : m,
            ),
          );
        }
      } finally {
        if (streamAbortRef.current === controller) {
          streamAbortRef.current = null;
        }
        liveAssistantIdRef.current = null;
        setIsStreaming(false);
        onSessionUpdate?.();
      }

      return sessionId;
    },
    [newChat, onSessionUpdate, onSessionStarted, processStream],
  );

  const loadSessionHistory = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`/sessions/${sessionId}/history`);
      if (!res.ok) return;
      const data = await res.json();
      const events = (data.events ?? []) as Record<string, unknown>[];
      const ctx = createEventContext();
      let turn = emptySessionTurn(sessionId);
      for (const event of events) {
        turn = applySessionEvent(turn, event, ctx);
      }
      turn = finalizeSessionTurn(turn, ctx);
      setSessionTurns((prev) => ({ ...prev, [sessionId]: { ...turn, sessionId } }));
    } catch {
      /* ignore */
    }
  }, []);

  const watchLiveSession = useCallback(
    async (sessionId: string) => {
      if (isStreaming && liveSessionRef.current === sessionId) return;
      try {
        const res = await fetch(`/sessions/${sessionId}/events`);
        if (!res.ok || !res.body) return;
        const ctx = createEventContext();
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";
          for (const part of parts) {
            const line = part.trim();
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6)) as Record<string, unknown>;
              setSessionTurns((prev) => {
                const turn = prev[sessionId] ?? emptySessionTurn(sessionId);
                return {
                  ...prev,
                  [sessionId]: {
                    ...applySessionEvent(turn, data, ctx),
                    sessionId,
                  },
                };
              });
            } catch {
              continue;
            }
          }
        }
        setSessionTurns((prev) => {
          const turn = prev[sessionId];
          if (!turn) return prev;
          return { ...prev, [sessionId]: finalizeSessionTurn(turn, ctx) };
        });
      } catch {
        /* ignore */
      }
    },
    [isStreaming],
  );

  return {
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
    liveSessionId: liveSessionRef.current,
  };
}
