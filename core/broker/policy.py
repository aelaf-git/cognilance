"""Tool risk grades and workspace approval policy.

Grades come from each tool's ``manifest.yaml``; this module only resolves them
and applies the workspace policy (which grades need a human approval).
"""

from __future__ import annotations

import os
from enum import Enum
from typing import Any


class RiskGrade(str, Enum):
    READ = "read"
    DRAFT = "draft"
    REVERSIBLE_WRITE = "reversible_write"
    IRREVERSIBLE = "irreversible"


# Built-ins that are not backed by a tools/<name>/manifest.yaml.
_BUILTIN_RISK: dict[str, RiskGrade] = {
    "thinking": RiskGrade.READ,
    "board.create": RiskGrade.READ,
}

# Legacy tool ids kept for old board rows / prompts.
_LEGACY_ALIASES: dict[str, str] = {
    "docs.create": "google_docs.create",
    "docs.write": "google_docs.write",
    "docs.read": "google_docs.read",
    "link.validate": "link_validate.check",
    "web.fetch_url": "web.fetch",
}


def canonical_tool_id(tool: str, action: str | None = None) -> str:
    key = tool.strip()
    if action and "." not in key:
        key = f"{key}.{action}"
    elif action and "." in key:
        key = f"{key.split('.', 1)[0]}.{action}"
    return _LEGACY_ALIASES.get(key, key)


def _manifest_risk(tool_id: str) -> RiskGrade | None:
    try:
        from tools.registry import tool_risk  # lazy: tools depends on core.broker
    except Exception:  # pragma: no cover - during partial installs
        return None
    grade = tool_risk(tool_id)
    if grade is None:
        return None
    try:
        return RiskGrade(grade)
    except ValueError:
        return None


def risk_for(tool: str, action: str | None = None) -> RiskGrade:
    key = canonical_tool_id(tool, action)
    if key in _BUILTIN_RISK:
        return _BUILTIN_RISK[key]
    manifest = _manifest_risk(key)
    if manifest is not None:
        return manifest
    # Legacy app:* mapping
    if key.startswith("app:gmail") and action == "send_email":
        return RiskGrade.IRREVERSIBLE
    if key.startswith("app:gmail") and action in {"compose_email", "draft"}:
        return RiskGrade.DRAFT
    if key.startswith("app:x") and action == "create_post":
        return RiskGrade.IRREVERSIBLE
    if key.startswith("app:reddit") and action == "submit_post":
        return RiskGrade.IRREVERSIBLE
    if key.startswith("app:linkedin") and action == "create_post":
        return RiskGrade.IRREVERSIBLE
    if key.startswith("app:"):
        return RiskGrade.REVERSIBLE_WRITE if action and "create" in action else RiskGrade.READ
    return RiskGrade.READ


def _env_grades_requiring_approval() -> set[RiskGrade]:
    raw = os.getenv("COGNILANCE_APPROVAL_GRADES", "irreversible").strip().lower()
    if raw in {"", "none", "off", "0"}:
        return set()
    grades: set[RiskGrade] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            grades.add(RiskGrade(token))
        except ValueError:
            continue
    return grades


def requires_approval(tool: str, action: str | None = None) -> bool:
    grade = risk_for(tool, action)
    return grade in _env_grades_requiring_approval()


def policy_snapshot() -> dict[str, Any]:
    try:
        from tools.registry import all_tool_risks
    except Exception:  # pragma: no cover
        all_tool_risks = dict  # type: ignore[assignment]
    return {
        "approval_grades": sorted(g.value for g in _env_grades_requiring_approval()),
        "tool_risk": {**{k: v.value for k, v in _BUILTIN_RISK.items()}, **all_tool_risks()},
    }
