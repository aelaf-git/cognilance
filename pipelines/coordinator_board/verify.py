"""Per-specialist output verification (hard fail → clarify)."""

from __future__ import annotations

import json
from typing import Any

from agents.loader import RolePack, coordinator
from core.models.gateway import get_structured_llm
from pipelines.coordinator_board.schema import VerificationResult
from pipelines.shared.streaming import emit, emit_status
from tools.link_validate.tool import extract_links, validate_links

_RESEARCH_HINTS = (
    "research",
    "search",
    "web",
    "http://",
    "https://",
    "news",
    "latest",
    "find",
    "look up",
    "sources",
    "cite",
    "url",
)

_GENERIC_CLARIFY = "I couldn't verify this result—what should I prioritize?"


def format_clarification_message(clarification: dict[str, Any]) -> str:
    """User-facing message: issues + questions; no roles/tools."""
    issues = [str(i).strip() for i in (clarification.get("issues") or []) if str(i).strip()]
    questions = [
        str(q).strip() for q in (clarification.get("questions") or []) if str(q).strip()
    ]
    if not questions:
        questions = [_GENERIC_CLARIFY]

    parts: list[str] = [
        "I need a bit more clarity before I continue.",
    ]
    if issues:
        parts.append("")
        parts.append("What I found:")
        parts.extend(f"- {issue}" for issue in issues[:5])
    parts.append("")
    parts.append("Could you clarify:")
    parts.extend(f"- {q}" for q in questions[:3])
    return "\n".join(parts)


def _heuristic_fail(text: str, data: dict[str, Any]) -> VerificationResult | None:
    stripped = (text or "").strip()
    if not stripped or stripped.lower() in {"no specialist results.", "no specialist results"}:
        return VerificationResult(
            passed=False,
            issues=["The task produced no usable output."],
            clarifying_questions=[
                "What exactly should I deliver for this request?",
            ],
            reasoning="empty_output",
        )
    if data.get("error"):
        return VerificationResult(
            passed=False,
            issues=[f"The task failed: {data.get('error')}"],
            clarifying_questions=[
                "How would you like me to proceed given that error?",
            ],
            reasoning="data_error",
        )
    return None


def _looks_like_research(instruction: str) -> bool:
    text = (instruction or "").lower()
    return any(h in text for h in _RESEARCH_HINTS)


async def _check_researcher_links(
    *,
    role_id: str,
    instruction: str,
    text: str,
) -> VerificationResult | None:
    if role_id != "researcher" or not _looks_like_research(instruction):
        return None
    urls = extract_links(text)
    if not urls:
        return None
    result = await validate_links(urls)
    broken = [
        row
        for row in (result.get("links") or [])
        if row.get("verdict") == "broken"
    ]
    if not broken:
        return None
    samples = [str(row.get("url") or "") for row in broken[:3] if row.get("url")]
    issue = "Some cited links look unreachable"
    if samples:
        issue += ": " + ", ".join(samples)
    return VerificationResult(
        passed=False,
        issues=[issue + "."],
        clarifying_questions=[
            "Should I continue without those sources, or do you have preferred links?",
        ],
        reasoning="broken_links",
    )


def _verify_prompt(
    *,
    rules: str,
    role_id: str,
    role_rules: str,
    instruction: str,
    text: str,
    data: dict[str, Any],
) -> str:
    data_snip = ""
    if data:
        try:
            data_snip = json.dumps(data, default=str)[:2000]
        except Exception:
            data_snip = str(data)[:2000]
    return (
        f"{rules.strip()}\n\n"
        f"Specialist role id (internal, do not mention to user): {role_id}\n"
        f"Role guidance:\n{role_rules.strip() or '(none)'}\n\n"
        f"Task instruction:\n{instruction}\n\n"
        f"Output text:\n{text}\n\n"
        f"Output data (may be empty):\n{data_snip or '(none)'}\n"
    )


async def verify_task_output(
    pack: RolePack,
    *,
    instruction: str,
    text: str,
    data: dict[str, Any] | None = None,
) -> VerificationResult:
    """Verify one specialist result. Fail closed if the verifier LLM errors."""
    emit_status("Verifying output…")
    payload = dict(data or {})

    heuristic = _heuristic_fail(text, payload)
    if heuristic is not None:
        emit("verify", passed=False, reason=heuristic.reasoning, issues=heuristic.issues)
        return heuristic

    link_fail = await _check_researcher_links(
        role_id=pack.id,
        instruction=instruction,
        text=text,
    )
    if link_fail is not None:
        emit("verify", passed=False, reason=link_fail.reasoning, issues=link_fail.issues)
        return link_fail

    coord = coordinator()
    rules = (coord.prompts.get("verify") or "").strip() or (
        "Verify the specialist output against the task. Fail closed when unsure."
    )
    role_rules = (pack.prompt("system") or pack.instructions or "").strip()

    try:
        llm = get_structured_llm(VerificationResult, temperature=0.05)
        result: VerificationResult = await llm.ainvoke(
            _verify_prompt(
                rules=rules,
                role_id=pack.id,
                role_rules=role_rules,
                instruction=instruction,
                text=text,
                data=payload,
            )
        )
    except Exception as exc:
        emit("verify", passed=False, reason="verifier_error", error=str(exc))
        return VerificationResult(
            passed=False,
            issues=["I could not verify this result reliably."],
            clarifying_questions=[_GENERIC_CLARIFY],
            reasoning="verifier_error",
        )

    if result.passed:
        emit("verify", passed=True, reasoning=result.reasoning)
        return result

    issues = list(result.issues) or ["The result did not meet the task requirements."]
    questions = list(result.clarifying_questions) or [_GENERIC_CLARIFY]
    cleaned = VerificationResult(
        passed=False,
        issues=issues,
        clarifying_questions=questions,
        reasoning=result.reasoning,
    )
    emit("verify", passed=False, reason=cleaned.reasoning, issues=cleaned.issues)
    return cleaned
