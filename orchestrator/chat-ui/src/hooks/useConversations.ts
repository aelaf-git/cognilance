import { useCallback, useEffect, useState } from "react";
import type { ConversationSummary, SessionSummary } from "@/types";

export function useConversations() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [conversationSessions, setConversationSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/conversations");
      if (!res.ok) return;
      const data = await res.json();
      setConversations(data.conversations ?? []);
    } catch {
      setConversations([]);
    }
  }, []);

  const loadConversationSessions = useCallback(async (conversationId: string) => {
    try {
      const res = await fetch(`/conversations/${conversationId}/sessions`);
      if (res.status === 404) {
        setConversationSessions([]);
        return null;
      }
      if (!res.ok) {
        setConversationSessions([]);
        return [];
      }
      const data = await res.json();
      const sessions = (data.sessions ?? []).map((s: SessionSummary) => ({
        ...s,
        session_type: s.session_type ?? "once",
      }));
      setConversationSessions(sessions);
      return sessions;
    } catch {
      setConversationSessions([]);
      return [];
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const selectConversation = useCallback(
    async (conversationId: string) => {
      setActiveSessionId(null);
      const sessions = await loadConversationSessions(conversationId);
      if (sessions === null) {
        setActiveConversationId(null);
        return null;
      }
      setActiveConversationId(conversationId);
      return sessions;
    },
    [loadConversationSessions],
  );

  const deleteConversation = useCallback(
    async (conversationId: string) => {
      let res = await fetch(`/conversations/${conversationId}`, { method: "DELETE" });
      if (res.status === 404 || res.status === 405) {
        res = await fetch(`/conversations/${conversationId}/delete`, { method: "POST" });
      }
      if (!res.ok) {
        let detail = "Could not delete conversation";
        try {
          const body = await res.json();
          detail = String(body.detail ?? detail);
        } catch {
          /* ignore */
        }
        window.alert(detail);
        return false;
      }
      if (activeConversationId === conversationId) {
        setActiveConversationId(null);
        setActiveSessionId(null);
        setConversationSessions([]);
      }
      await refresh();
      return true;
    },
    [activeConversationId, refresh],
  );

  const abortSession = useCallback(
    async (sessionId: string) => {
      await fetch(`/sessions/${sessionId}/abort`, { method: "POST" });
      if (activeConversationId) {
        await loadConversationSessions(activeConversationId);
      }
      await refresh();
    },
    [activeConversationId, loadConversationSessions, refresh],
  );

  const stopSubscription = useCallback(
    async (subscriptionId: string) => {
      const res = await fetch(`/subscriptions/${subscriptionId}/stop`, { method: "POST" });
      if (!res.ok) return false;
      await refresh();
      if (activeConversationId) {
        await loadConversationSessions(activeConversationId);
      }
      return true;
    },
    [activeConversationId, loadConversationSessions, refresh],
  );

  return {
    conversations,
    activeConversationId,
    setActiveConversationId,
    conversationSessions,
    activeSessionId,
    setActiveSessionId,
    refresh,
    selectConversation,
    deleteConversation,
    loadConversationSessions,
    abortSession,
    stopSubscription,
  };
}
