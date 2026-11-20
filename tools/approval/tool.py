"""Pause the current run. The request is read-only and writes no organization row."""

from __future__ import annotations

import json
from typing import Any

from core.context.request import current_mission_id
from core.runtime.runs.store import RunStore
from tools.registry import ApprovalRequired, ToolContext, ToolOutput


def _instruction_params(instruction: str, params: dict[str, Any]) -> dict[str, Any]:
    body = dict(params or {})
    text = str(instruction or "").strip()
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            body = {**parsed, **body}
    elif text and "reason" not in body:
        body["reason"] = text
    body.pop("organization_id", None)
    return body


def _organization_id() -> str:
    run_id = str(current_mission_id.get() or "").strip()
    if not run_id:
        return ""
    run = RunStore().get_run(run_id)
    if run is None:
        return ""
    return str(run.organization_id or "")


def _invalid(fields: list[str]) -> ToolOutput:
    names = ", ".join(fields)
    return ToolOutput(
        text=f"Invalid parameters: {names}",
        data={"error": "invalid_params", "fields": fields},
        status="error",
    )


async def run(
    action: str,
    *,
    instruction: str,
    params: dict[str, Any],
    ctx: ToolContext,
) -> ToolOutput:
    if action != "request":
        raise RuntimeError(f"Unknown approval action: {action}")
    if not _organization_id():
        return ToolOutput(
            text="No organization is set for this run.",
            data={"error": "no organization"},
            status="error",
        )
    body = _instruction_params(instruction, params)
    reason = str(body.get("reason") or "").strip()
    if not reason:
        return _invalid(["reason"])
    raise ApprovalRequired(ctx.tool_id, "request", {"reason": reason}, ctx.risk)
