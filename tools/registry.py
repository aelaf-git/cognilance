"""Tool registry: loads ``tools/<name>/manifest.yaml`` and dispatches calls.

A tool id is ``<tool>.<action>`` (e.g. ``gmail.draft``). Each tool folder has
``manifest.yaml`` (id, actions, risk grades) and ``tool.py`` exposing::

    async def run(action: str, *, instruction: str, params: dict, ctx: ToolContext) -> ToolOutput

Agents may only call tool ids listed in their ``agent.yaml``.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.broker.policy import canonical_tool_id, requires_approval, risk_for
from core.context.request import current_user_id

TOOLS_DIR = Path(__file__).resolve().parent


class ApprovalRequired(Exception):
    """Raised when a tool call needs human approval before continuing."""

    def __init__(self, tool: str, action: str | None, params: dict[str, Any], risk: str):
        self.tool = tool
        self.action = action
        self.params = params
        self.risk = risk
        super().__init__(f"Approval required for {tool}" + (f".{action}" if action else ""))


@dataclass
class ToolManifest:
    id: str
    name: str
    description: str
    actions: dict[str, dict[str, Any]]  # action -> {risk, description, integration?}
    integration: str | None = None
    path: Path | None = None

    def tool_ids(self) -> list[str]:
        return [f"{self.id}.{a}" for a in self.actions]


@dataclass
class ToolContext:
    role_id: str
    user_id: str
    client: Any  # core.broker.client.IntegrationClient
    tool_id: str
    risk: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutput:
    text: str
    data: dict[str, Any] = field(default_factory=dict)
    status: str = "completed"


def _parse_manifest(path: Path) -> ToolManifest:
    raw = yaml.safe_load(path.read_text()) or {}
    actions_raw = raw.get("actions") or {}
    actions: dict[str, dict[str, Any]] = {}
    if isinstance(actions_raw, list):
        for item in actions_raw:
            if isinstance(item, str):
                actions[item] = {"risk": "read"}
            elif isinstance(item, dict) and item.get("id"):
                actions[str(item["id"])] = {k: v for k, v in item.items() if k != "id"}
    elif isinstance(actions_raw, dict):
        for key, value in actions_raw.items():
            actions[str(key)] = dict(value or {}) if isinstance(value, dict) else {"risk": str(value)}
    return ToolManifest(
        id=str(raw.get("id") or path.parent.name),
        name=str(raw.get("name") or path.parent.name),
        description=str(raw.get("description") or ""),
        actions=actions,
        integration=raw.get("integration"),
        path=path,
    )


@lru_cache(maxsize=1)
def load_manifests() -> dict[str, ToolManifest]:
    manifests: dict[str, ToolManifest] = {}
    for manifest_path in sorted(TOOLS_DIR.glob("*/manifest.yaml")):
        manifest = _parse_manifest(manifest_path)
        manifests[manifest.id] = manifest
    return manifests


def all_tool_ids() -> list[str]:
    ids: list[str] = []
    for manifest in load_manifests().values():
        ids.extend(manifest.tool_ids())
    return ids


def tool_risk(tool_id: str) -> str | None:
    base, _, action = canonical_tool_id(tool_id).partition(".")
    manifest = load_manifests().get(base)
    if not manifest or action not in manifest.actions:
        return None
    return str(manifest.actions[action].get("risk") or "read")


def all_tool_risks() -> dict[str, str]:
    out: dict[str, str] = {}
    for manifest in load_manifests().values():
        for action, spec in manifest.actions.items():
            out[f"{manifest.id}.{action}"] = str(spec.get("risk") or "read")
    return out


def validate_tool_ids(tool_ids: list[str]) -> list[str]:
    """Return unknown tool ids (empty list when everything resolves)."""
    known = set(all_tool_ids()) | {"thinking", "board.create"}
    return [t for t in tool_ids if canonical_tool_id(t) not in known]


def is_allowed(role_tools: list[str] | tuple[str, ...], tool_id: str) -> bool:
    canonical = canonical_tool_id(tool_id)
    if canonical == "thinking":
        return True
    allowed = {canonical_tool_id(t) for t in role_tools}
    if canonical in allowed:
        return True
    # wildcard "gmail.*"
    base = canonical.split(".", 1)[0]
    return f"{base}.*" in allowed


def _tool_module(base: str):
    return importlib.import_module(f"tools.{base}.tool")


async def run_tool(
    role: Any,
    tool: str,
    *,
    instruction: str = "",
    params: dict[str, Any] | None = None,
    integrations: Any | None = None,
    skip_approval_check: bool = False,
    conversation: list[Any] | None = None,
) -> dict[str, Any]:
    """Run one tool on behalf of a role. Returns ``{text,data,assignee,risk,status}``."""
    from agents.loader import RolePack, get_role
    from core.broker.client import IntegrationClient
    from pipelines.shared.streaming import emit

    pack: RolePack | None = get_role(role) if isinstance(role, str) else role
    if pack is None:
        raise RuntimeError(f"Unknown role: {role}")

    tool_id = canonical_tool_id(tool)
    if not is_allowed(pack.tools, tool_id):
        raise RuntimeError(f"Role {pack.id} is not allowed to use tool {tool_id}")

    params = dict(params or {})
    base, _, action = tool_id.partition(".")
    risk = risk_for(tool_id)
    if not skip_approval_check and requires_approval(tool_id):
        raise ApprovalRequired(tool_id, action or None, params, risk.value)

    emit("tool_start", tool=tool_id, assignee=pack.id, risk=risk.value)
    client = integrations or IntegrationClient()
    user_id = current_user_id.get() or ""

    if base == "thinking":
        from core.models.thinking import run_thinking

        text, data = await run_thinking(
            instruction or params.get("query", ""),
            stream=False,
            conversation=conversation,
            capabilities=client.capabilities_context(user_id),
        )
        output = ToolOutput(text=text, data=data)
    else:
        manifest = load_manifests().get(base)
        if manifest is None or action not in manifest.actions:
            raise RuntimeError(f"Unhandled tool: {tool_id}")
        ctx = ToolContext(
            role_id=pack.id,
            user_id=user_id,
            client=client,
            tool_id=tool_id,
            risk=risk.value,
        )
        output = await _tool_module(base).run(action, instruction=instruction, params=params, ctx=ctx)
        if not isinstance(output, ToolOutput):
            output = ToolOutput(text=str(output.get("text") or ""), data=dict(output.get("data") or {}))

    emit("tool_done", tool=tool_id, assignee=pack.id, status=output.status)
    return {
        "text": output.text,
        "data": output.data,
        "assignee": pack.id,
        "risk": risk.value,
        "status": output.status,
    }


# Backwards-compatible name used by older pipeline code.
run_role_tool = run_tool

__all__ = [
    "ApprovalRequired",
    "ToolContext",
    "ToolManifest",
    "ToolOutput",
    "all_tool_ids",
    "all_tool_risks",
    "is_allowed",
    "load_manifests",
    "run_role_tool",
    "run_tool",
    "tool_risk",
    "validate_tool_ids",
]
