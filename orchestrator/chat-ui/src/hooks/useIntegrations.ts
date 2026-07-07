import { useCallback, useEffect, useState } from "react";
import type { AppIntegration } from "@/types";

export function useIntegrations() {
  const [integrations, setIntegrations] = useState<AppIntegration[]>([]);
  const [banner, setBanner] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/integrations/list");
      if (!res.ok) return;
      const data = await res.json();
      setIntegrations(data.integrations ?? data.apps ?? []);
    } catch {
      setIntegrations([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    const error = params.get("error");
    if (connected) {
      setBanner(`Successfully connected ${connected.replace("-", " ")}.`);
      window.history.replaceState({}, "", "/integrations");
    } else if (error) {
      setBanner(`Connection failed: ${error}`);
      window.history.replaceState({}, "", "/integrations");
    }
  }, [refresh]);

  const connect = useCallback((integrationId: string) => {
    window.location.href = `/integrations/${integrationId}/connect`;
  }, []);

  const disconnect = useCallback(
    async (integrationId: string) => {
      await fetch(`/integrations/${integrationId}/disconnect`, { method: "POST" });
      await refresh();
    },
    [refresh],
  );

  return { integrations, refresh, connect, disconnect, banner };
}
