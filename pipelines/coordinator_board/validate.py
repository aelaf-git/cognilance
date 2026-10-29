"""Code checks for actions, briefs, and specialist payloads.

The model proposes an action. These checks reject it before any specialist runs.
"""

from __future__ import annotations

import re
from typing import Any

from agents.loader import get_role, normalize_role_id
from pipelines.coordinator_board.models import (
    Brief,
    Delegation,
    ObservationStatus,
    Roster,
    ThinkDecision,
)

# Orchestrator-level tools. Specialists own their own tools. None are registered here.
ORCHESTRATOR_TOOLS: frozenset[str] = frozenset()

_TRIVIAL = re.compile(
    r"^(?:hey|hi|hello|yo|thanks|thank you|ok|okay|cool|goodbye|bye)[!.?\s]*$",
    re.IGNORECASE,
)

_MIN_GOAL = 8


def trivial_reply(user_text: str) -> str | None:
    """A pure greeting needs no specialist. Returns the reply, or None."""
    match = _TRIVIAL.match((user_text or "").strip())
    if match is None:
        return None
    word = match.group(0).strip().lower().rstrip(".!?")
    if word in {"thanks", "thank you"}:
        return "You're welcome."
    if word in {"bye", "goodbye"}:
        return "Talk later."
    if word in {"ok", "okay", "cool"}:
        return "Sounds good."
    return "Hey. What can I help with?"


def apply_trivial_guard(user_text: str, decision: ThinkDecision) -> ThinkDecision:
    """Refuse tool use and delegation when the whole message is chitchat."""
    reply = trivial_reply(user_text)
    if reply is None or decision.action in {"answer_directly", "ask_user", "finish"}:
        return decision
    return decision.model_copy(
        update={
            "action": "answer_directly",
            "direct_answer": reply,
            "delegations": [],
            "tool_id": "",
            "status_line": "",
        }
    )


def brief_problem(brief: Brief) -> str | None:
    if len((brief.goal or "").strip()) < _MIN_GOAL:
        return "vague brief"
    if not any(str(item).strip() for item in brief.success_criteria):
        return "vague brief"
    return None


def _error_observation(source: str, error: str, *, agent_id: str = "") -> dict[str, Any]:
    return {
        "source": source or "orchestrator",
        "status": "error",
        "payload": {
            "untrusted": True,
            "error": error,
            "agent_id": agent_id,
            "text": "",
        },
    }


def split_delegations(
    decision: ThinkDecision,
    roster: Roster,
) -> tuple[list[Delegation], list[dict[str, Any]]]:
    """Keep delegations that name an available agent and a concrete brief.

    Rejected delegations become error observations and are not executed.
    """
    by_id = {agent.id: agent for agent in roster.agents}
    accepted: list[Delegation] = []
    errors: list[dict[str, Any]] = []
    for item in decision.delegations:
        agent_id = normalize_role_id(item.agent_id or "")
        entry = by_id.get(agent_id)
        if entry is None:
            errors.append(
                _error_observation("orchestrator", "no such agent", agent_id=item.agent_id)
            )
            continue
        if entry.status != "available":
            errors.append(
                _error_observation("orchestrator", "agent offline", agent_id=entry.id)
            )
            continue
        problem = brief_problem(item.brief)
        if problem:
            errors.append(_error_observation(entry.id, problem, agent_id=entry.id))
            continue
        accepted.append(item.model_copy(update={"agent_id": agent_id}))
    return accepted, errors


def _meaningful(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_meaningful(item) for item in value.values())
    if isinstance(value, list):
        return any(_meaningful(item) for item in value)
    return value not in (None, "", [], {})


def classify_payload(agent_id: str | None, payload: dict[str, Any] | None) -> ObservationStatus:
    """Deterministic status before any LLM judge runs."""
    body = dict(payload or {})
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    if body.get("error") or data.get("error"):
        return "error"
    result = body.get("result")
    if result is None and isinstance(data, dict):
        result = data.get("result")
    if agent_id and isinstance(result, dict):
        pack = get_role(agent_id)
        schema = None
        if pack is not None:
            try:
                schema = pack.result_schema()
            except Exception:  # noqa: BLE001
                schema = None
        if schema is not None:
            known = set(getattr(schema, "model_fields", {}) or {})
            if known and not known.intersection(result):
                return "partial"
            try:
                schema.model_validate(result)
            except Exception:  # noqa: BLE001
                return "partial"
    text = str(body.get("text") or "").strip()
    if not text and not _meaningful(data) and not _meaningful(result if isinstance(result, dict) else None):
        return "empty"
    return "ok"
