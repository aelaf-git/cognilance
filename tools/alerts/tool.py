"""Organization alerts. A missing organization is reported before any row is written."""

from __future__ import annotations

import json
from typing import Any

from core.context.orgs.store import OrgStore
from core.context.request import current_mission_id
from core.runtime.runs.store import RunStore
from tools.registry import ToolContext, ToolOutput

_SEVERITIES = ("info", "warning", "critical")


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
    elif text and "summary" not in body:
        body["summary"] = text
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
    if action != "create":
        raise RuntimeError(f"Unknown alerts action: {action}")
    organization_id = _organization_id()
    if not organization_id:
        return ToolOutput(
            text="No organization is set for this run.",
            data={"error": "no organization"},
            status="error",
        )
    body = _instruction_params(instruction, params)
    summary = str(body.get("summary") or "").strip()
    if not summary:
        return _invalid(["summary"])
    severity = str(body.get("severity") or "info").strip().lower()
    if severity not in _SEVERITIES:
        return _invalid(["severity"])
    kind = str(body.get("kind") or "info").strip() or "info"
    alert = OrgStore().add_alert(
        organization_id,
        summary,
        kind=kind,
        severity=severity,
    )
    return ToolOutput(
        text=alert.summary,
        data={
            "alert": {
                "id": alert.id,
                "organization_id": alert.organization_id,
                "kind": alert.kind,
                "summary": alert.summary,
                "severity": alert.severity,
            }
        },
    )
