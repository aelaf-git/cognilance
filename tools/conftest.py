"""Shared fixtures for tool tests."""

from __future__ import annotations

from typing import Any

import pytest

from tools.registry import ToolContext


class FakeClient:
    """Minimal stand-in for core.broker.client.IntegrationClient."""

    def __init__(self, connected: set[str] | None = None, responses: dict[str, Any] | None = None):
        self._connected = connected or set()
        self._responses = responses or {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def is_connected(self, user_id: str, integration_id: str) -> bool:
        return integration_id in self._connected

    async def run(self, user_id: str, integration_id: str, action: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((integration_id, action, dict(params)))
        return dict(self._responses.get(action) or {})

    def summarize_result(self, integration_id: str, action: str, result: dict[str, Any]) -> str:
        return f"{integration_id}.{action}: {result}"

    def capabilities_context(self, user_id: str) -> str:
        return ""


@pytest.fixture
def make_ctx():
    def _make(tool_id: str, *, client: FakeClient | None = None, role_id: str = "tester") -> ToolContext:
        return ToolContext(
            role_id=role_id,
            user_id="u-test",
            client=client or FakeClient(),
            tool_id=tool_id,
            risk="read",
        )

    return _make
