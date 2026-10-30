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


_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "for",
        "of",
        "and",
        "or",
        "with",
        "about",
        "on",
        "in",
        "into",
        "from",
        "please",
        "can",
        "you",
        "hey",
        "generate",
        "create",
        "write",
        "draft",
        "make",
        "send",
        "post",
        "email",
        "research",
        "do",
        "prepare",
        "just",
        "document",
        "documents",
        "docx",
        "word",
        "file",
        "files",
        "page",
        "pages",
        "paragraph",
        "paragraphs",
        "report",
        "reports",
        "google",
        "doc",
        "docs",
        "drive",
        "me",
        "my",
        "it",
        "this",
        "that",
        "one",
        "something",
        "two",
        "three",
        "four",
        "five",
    }
)
_CREATE = re.compile(r"\b(?:generate|create|write|draft|make|prepare)\b", re.IGNORECASE)
_LOCAL_DOC = re.compile(r"\b(?:documents?|docx|word file)\b", re.IGNORECASE)
_GOOGLE_DOC = re.compile(r"google\s+docs?|google\s+drive", re.IGNORECASE)
_UNRECOVERABLE = ("not connected", "not allowed to use tool", "unhandled tool")


def _content_words(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", (text or "").lower())
    return [word for word in words if word not in _STOP_WORDS and len(word) > 1]


def vague_question(user_text: str, conversation: str = "") -> str | None:
    """One follow-up when the request names no subject, recipient, or item.

    A greeting is not vague. A conversation that already names the subject is enough.
    """
    text = (user_text or "").strip()
    if not text or trivial_reply(text) is not None:
        return None
    if _content_words(text) or _content_words(conversation):
        return None
    lowered = text.lower()
    if _LOCAL_DOC.search(lowered) or "report" in lowered or "page" in lowered:
        return "What should the document be about?"
    if any(word in lowered for word in ("send", "email", "mail", "post")):
        return "Who should I send it to?"
    return "What should I focus on?"


def apply_vague_guard(user_text: str, conversation: str, decision: ThinkDecision) -> ThinkDecision:
    """Ask one question and stop when the request itself is vague."""
    if decision.action == "ask_user" and (decision.question or "").strip():
        return decision
    question = vague_question(user_text, conversation)
    if question is None:
        return decision
    return decision.model_copy(
        update={
            "action": "ask_user",
            "question": question,
            "delegations": [],
            "direct_answer": "",
            "finish_answer": "",
            "tool_id": "",
            "status_line": "",
        }
    )


def wants_local_document(user_text: str) -> bool:
    text = user_text or ""
    if _GOOGLE_DOC.search(text):
        return False
    return bool(_CREATE.search(text) and _LOCAL_DOC.search(text))


def concrete_brief(user_text: str, brief: Brief) -> Brief:
    """Fill a thin brief from a specific user request. Never invent a missing subject."""
    goal = (brief.goal or "").strip()
    if len(goal) < _MIN_GOAL:
        goal = (user_text or "").strip()[:500] or goal
    original_criteria = [str(item).strip() for item in brief.success_criteria if str(item).strip()]
    criteria = list(original_criteria) or ["The result meets the user's request."]
    if goal == (brief.goal or "").strip() and criteria == original_criteria:
        return brief
    return brief.model_copy(update={"goal": goal, "success_criteria": criteria})


def _word_brief(user_text: str, decision: ThinkDecision) -> Brief:
    source = decision.delegations[0].brief if decision.delegations else Brief()
    goal = (user_text or "").strip()
    if len(goal) < _MIN_GOAL:
        goal = (source.goal or decision.user_ask or "Write the requested Word document.").strip()
    constraints = [
        str(item).strip()
        for item in source.constraints
        if str(item).strip() and "google" not in str(item).lower()
    ]
    if not any("word" in item.lower() for item in constraints):
        constraints.append("Write a Word file.")
    criteria = [
        str(item).strip()
        for item in source.success_criteria
        if str(item).strip() and "google" not in str(item).lower()
    ]
    word_goal = "A Word file is saved and covers the requested topic."
    if word_goal not in criteria:
        criteria.insert(0, word_goal)
    context = str(source.context or "").strip()
    if "google" in context.lower():
        context = goal
    return Brief(
        goal=goal[:500],
        context=context,
        constraints=constraints,
        success_criteria=criteria,
        budget=source.budget or "one pass",
    )


def apply_document_guard(user_text: str, decision: ThinkDecision) -> ThinkDecision:
    """A document the user did not call a Google Doc is one Word brief."""
    if decision.action == "ask_user" or not wants_local_document(user_text):
        return decision
    if (
        decision.action == "delegate"
        and len(decision.delegations) == 1
        and decision.delegations[0].agent_id == "docx_agent"
        and not any("google" in str(item).lower() for item in decision.delegations[0].brief.constraints)
        and not any("google" in str(item).lower() for item in decision.delegations[0].brief.success_criteria)
    ):
        return decision
    return decision.model_copy(
        update={
            "action": "delegate",
            "delegations": [Delegation(agent_id="docx_agent", brief=_word_brief(user_text, decision))],
            "direct_answer": "",
            "finish_answer": "",
            "tool_id": "",
            "status_line": decision.status_line,
        }
    )


def integration_failure(error: str) -> bool:
    lowered = (error or "").lower()
    return any(mark in lowered for mark in _UNRECOVERABLE)


def blocked_agents(observations: list[dict[str, Any]]) -> dict[str, str]:
    """Agents whose last failure cannot be fixed by another brief."""
    blocked: dict[str, str] = {}
    for obs in observations or []:
        if obs.get("status") != "error":
            continue
        error = str((obs.get("payload") or {}).get("error") or "")
        source = str(obs.get("source") or "")
        if source and source != "orchestrator" and integration_failure(error):
            blocked[source] = error
    return blocked


def apply_integration_guard(
    user_text: str,
    decision: ThinkDecision,
    observations: list[dict[str, Any]],
) -> ThinkDecision:
    """Do not delegate an agent that already failed because the integration is down."""
    blocked = blocked_agents(observations)
    if decision.action != "delegate" or not blocked:
        return decision
    kept: list[Delegation] = []
    errors: list[str] = []
    added_word = False
    for item in decision.delegations:
        if item.agent_id not in blocked:
            kept.append(item)
            continue
        errors.append(blocked[item.agent_id])
        if wants_local_document(user_text) and "docx_agent" not in blocked and not added_word:
            kept.append(Delegation(agent_id="docx_agent", brief=_word_brief(user_text, decision)))
            added_word = True
    if kept:
        return decision.model_copy(update={"action": "delegate", "delegations": kept})
    reason = errors[0] if errors else next(iter(blocked.values()))
    return decision.model_copy(
        update={
            "action": "finish",
            "finish_answer": reason,
            "delegations": [],
            "direct_answer": "",
            "tool_id": "",
            "status_line": "",
        }
    )


def repair_specific_briefs(user_text: str, conversation: str, decision: ThinkDecision) -> ThinkDecision:
    """A specific request keeps its subject when the model wrote a thin brief."""
    if decision.action != "delegate" or vague_question(user_text, conversation):
        return decision
    repaired = [
        item.model_copy(update={"brief": concrete_brief(user_text, item.brief)})
        for item in decision.delegations
    ]
    return decision.model_copy(update={"delegations": repaired})


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
