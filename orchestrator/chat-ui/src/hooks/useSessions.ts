import { useCallback, useEffect, useState } from "react";
import type { SessionSummary } from "@/types";

export function useSessions() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/sessions");
      if (!res.ok) return;
      const data = await res.json();
      setSessions(
        (data.sessions ?? data.missions ?? []).map((s: SessionSummary) => ({
          ...s,
          session_type: s.session_type ?? "once",
        })),
      );
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const abortSession = useCallback(
    async (sessionId: string) => {
      await fetch(`/sessions/${sessionId}/abort`, { method: "POST" });
      await refresh();
    },
    [refresh],
  );

  const dismissSession = useCallback(
    async (sessionId: string) => {
      const res = await fetch(`/sessions/${sessionId}/dismiss`, { method: "POST" });
      if (!res.ok) {
        let detail = "Could not remove session";
        try {
          const body = await res.json();
          detail = String(body.detail ?? detail);
        } catch {
          /* ignore */
        }
        window.alert(detail);
        return;
      }
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
      }
      await refresh();
    },
    [activeSessionId, refresh],
  );

  return {
    sessions,
    activeSessionId,
    setActiveSessionId,
    refresh,
    abortSession,
    dismissSession,
  };
}
