"""Live roster from agent manifests, plus capabilities no agent covers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agents.loader import COORDINATOR_ID, load_roles
from pipelines.coordinator_board.models import Roster, RosterEntry

_CAPABILITIES = Path(__file__).with_name("capabilities.yaml")


def _annotation_name(annotation: Any) -> str:
    name = getattr(annotation, "__name__", None)
    if isinstance(name, str) and name:
        return name
    return "any"


def _output_shape(pack: Any) -> dict[str, str]:
    try:
        model = pack.result_schema()
    except Exception:  # noqa: BLE001
        return {}
    if model is None:
        return {}
    fields = getattr(model, "model_fields", None) or {}
    return {name: _annotation_name(field.annotation) for name, field in fields.items()}


def _capability_gaps(tool_ids: set[str]) -> list[str]:
    raw = yaml.safe_load(_CAPABILITIES.read_text()) or {}
    gaps: list[str] = []
    for item in raw.get("capabilities") or []:
        if not isinstance(item, dict):
            continue
        tools = [str(t) for t in (item.get("tools") or [])]
        if tools and tool_ids.intersection(tools):
            continue
        label = str(item.get("label") or "").strip()
        if label:
            gaps.append(label)
    return gaps


def build_roster() -> Roster:
    """Re-read manifests so a turn sees agents added or removed on disk."""
    load_roles.cache_clear()
    roles = load_roles()
    entries: list[RosterEntry] = []
    tool_ids: set[str] = set()
    for role_id, pack in roles.items():
        if role_id == COORDINATOR_ID:
            continue
        tools = [str(t) for t in pack.tools]
        tool_ids.update(tools)
        entries.append(
            RosterEntry(
                id=pack.id,
                description=pack.description or pack.instructions,
                required_inputs=tools,
                output_shape=_output_shape(pack),
                limits=pack.description or "none recorded",
                status="available",
            )
        )
    entries.sort(key=lambda entry: entry.id)
    return Roster(agents=entries, not_available=_capability_gaps(tool_ids))
