"""Runtime integration client for manager agent tool calls."""

from __future__ import annotations

import json
from typing import Any

from orchestrator.integrations.executor import IntegrationExecutor
from orchestrator.integrations.registry import INTEGRATIONS, list_integrations
from orchestrator.integrations.token_manager import TokenManager
from orchestrator.streaming import emit


class IntegrationClient:
    def __init__(self, token_manager: TokenManager | None = None) -> None:
        self._tokens = token_manager or TokenManager()
        self._executor = IntegrationExecutor()

    def is_connected(self, user_id: str, integration_id: str) -> bool:
        return self._tokens.is_connected(user_id, integration_id)

    def capabilities_context(self, user_id: str) -> str:
        """Full tool inventory with connection status for planner and thinking agents."""
        connected = set(self._tokens.list_connected(user_id))
        lines = [
            "=== Orchestrator capabilities ===",
            "",
            "Always available:",
            "- thinking — reason and answer directly (no external APIs)",
            "- hire:<skill> — delegate to a marketplace agent (skill must exist in catalog)",
            "",
            "OAuth integrations (only usable when CONNECTED):",
        ]
        for spec in list_integrations():
            integration_id = spec["id"]
            is_on = integration_id in connected
            status = "CONNECTED" if is_on else "NOT CONNECTED"
            actions = ", ".join(spec["actions"])
            lines.append(f"- app:{integration_id} — {spec['name']} [{status}]")
            lines.append(f"  {spec['description']}")
            lines.append(f"  Actions: {actions}")
            if is_on:
                lines.append(f"  → You may plan subtasks with tool=app:{integration_id}")
                if integration_id == "google-drive":
                    lines.append(
                        "  Google Docs: create_document {name, content}; "
                        "write_document {document_id, content, mode, style:{bold, font_size, font_family}}"
                    )
            else:
                lines.append(
                    f"  → Do NOT use app:{integration_id}. "
                    f"Tell the user to connect {spec['name']} at /integrations first."
                )
            lines.append("")
        lines.append(
            "Decision rules: Only route to app:* tools that are CONNECTED. "
            "If the user needs a disconnected integration, use thinking and explain how to connect."
        )
        return "\n".join(lines)

    def available_tools_text(self, user_id: str) -> str:
        """Connected tools only (legacy summary)."""
        lines = ["- thinking — answer directly with reasoning"]
        lines.append("- hire:<skill> — hire a marketplace agent by skill slug")
        connected = self._tokens.list_connected(user_id)
        for spec in list_integrations():
            if spec["id"] not in connected:
                continue
            actions = ", ".join(spec["actions"])
            lines.append(f"- app:{spec['id']} — {spec['name']} (actions: {actions})")
        return "\n".join(lines)

    async def run(
        self,
        user_id: str,
        integration_id: str,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        spec = INTEGRATIONS.get(integration_id)
        if not spec:
            raise RuntimeError(f"Unknown integration: {integration_id}")
        emit("tool_start", tool=f"app:{integration_id}", assignee=integration_id, action=action)
        token = await self._tokens.get_access_token(user_id, integration_id)
        result = await self._executor.execute(integration_id, token, action, params or {})
        emit("tool_done", tool=f"app:{integration_id}", assignee=integration_id, status="completed")
        return result

    def summarize_result(self, integration_id: str, action: str, result: dict[str, Any]) -> str:
        try:
            return json.dumps(result, default=str)[:4000]
        except TypeError:
            return str(result)[:4000]
