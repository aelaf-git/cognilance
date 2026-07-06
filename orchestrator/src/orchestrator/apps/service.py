"""App integration catalog and connection status."""

from __future__ import annotations

import os
from typing import Any

from orchestrator.apps.store import AppStore

_BUILTIN_APPS: list[dict[str, str]] = [
    {
        "id": "telegram",
        "name": "Telegram",
        "description": "Send messages via Telegram Bot API.",
        "category": "communication",
    },
    {
        "id": "discord",
        "name": "Discord",
        "description": "Send messages to a Discord channel or webhook.",
        "category": "communication",
    },
]


class AppService:
    def __init__(self, store: AppStore | None = None) -> None:
        self._store = store or AppStore()
        self._store.init_db()

    def get_credentials(self, app_id: str) -> dict[str, Any]:
        stored = self._store.get_credentials(app_id) or {}
        if app_id == "telegram":
            env_keys = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
        elif app_id == "discord":
            env_keys = ("DISCORD_WEBHOOK_URL", "DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID")
        else:
            return stored
        merged = {key: os.getenv(key, "") for key in env_keys}
        merged.update({k: v for k, v in stored.items() if v})
        return merged

    def list_apps(self) -> list[dict[str, Any]]:
        apps: list[dict[str, Any]] = []
        for app in _BUILTIN_APPS:
            connected = self._is_connected(app["id"])
            apps.append({**app, "connected": connected})
        return apps

    def _is_connected(self, app_id: str) -> bool:
        if self._store.get_credentials(app_id):
            return True
        if app_id == "telegram":
            return bool(os.getenv("TELEGRAM_BOT_TOKEN"))
        if app_id == "discord":
            return bool(os.getenv("DISCORD_WEBHOOK_URL") or os.getenv("DISCORD_BOT_TOKEN"))
        return False

    def connect(self, app_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        self._store.set_credentials(app_id, credentials)
        return {"app_id": app_id, "connected": True}

    def disconnect(self, app_id: str) -> dict[str, Any]:
        self._store.disconnect(app_id)
        return {"app_id": app_id, "connected": False}

    def available_tools_text(self) -> str:
        lines = ["- hire:<skill> — hire a marketplace agent by skill slug"]
        for app in self.list_apps():
            if app["connected"]:
                lines.append(f"- app:{app['id']} — {app['name']} (connected)")
        return "\n".join(lines)

    def is_app_connected(self, app_id: str) -> bool:
        return self._is_connected(app_id)
