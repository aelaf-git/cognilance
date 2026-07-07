import { useCallback, useEffect, useState } from "react";
import type { AppIntegration } from "@/types";

export function useApps() {
  const [apps, setApps] = useState<AppIntegration[]>([]);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/apps");
      if (!res.ok) return;
      const data = await res.json();
      setApps(data.apps ?? []);
    } catch {
      setApps([]);
    }
  }, []);

  const connect = useCallback(
    async (appId: string) => {
      const credentials: Record<string, string> = {};
      if (appId === "telegram") {
        const token = window.prompt("Telegram bot token (or leave blank to use env TELEGRAM_BOT_TOKEN)");
        if (token) credentials.TELEGRAM_BOT_TOKEN = token;
        const chatId = window.prompt("Telegram chat ID (or leave blank to use env TELEGRAM_CHAT_ID)");
        if (chatId) credentials.TELEGRAM_CHAT_ID = chatId;
      } else if (appId === "discord") {
        const webhook = window.prompt("Discord webhook URL (or leave blank to use env DISCORD_WEBHOOK_URL)");
        if (webhook) credentials.DISCORD_WEBHOOK_URL = webhook;
        const token = window.prompt("Discord bot token (optional, if not using webhook)");
        if (token) credentials.DISCORD_BOT_TOKEN = token;
        const channelId = window.prompt("Discord channel ID (required with bot token)");
        if (channelId) credentials.DISCORD_CHANNEL_ID = channelId;
      }
      await fetch(`/apps/${appId}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credentials }),
      });
      await refresh();
    },
    [refresh],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { apps, refresh, connect };
}
