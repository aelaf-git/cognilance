"""Task Agent — decompose plan, delegate subtasks in parallel layers, aggregate results."""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict, deque
from typing import Any, Literal

from cognilance import CognilanceManager

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from orchestrator.integrations.client import IntegrationClient
from orchestrator.integrations.gmail_params import format_email_draft, format_send_email_result
from orchestrator.presenters.results import (
    format_calendar_list_result,
    format_document_result,
    format_gmail_list_result,
    format_recurring_result,
    format_subscription_result,
)
from orchestrator.tools.web import format_web_fetch_result, format_web_search_result
from orchestrator.llm import get_llm, get_structured_llm, last_user_text, to_chat_messages
from orchestrator.state import State, Subtask, SubtaskResult
from orchestrator.streaming import emit, emit_status, stream_llm
from orchestrator.tools.router import ToolRouter
from orchestrator.drafts.store import DraftStore
from orchestrator.integrations.gmail_params import mark_email_draft_sent


def _conversation_history(
    messages: list[BaseMessage] | None,
    *,
    limit: int = 24,
) -> list[dict[str, str]]:
    if not messages:
        return []
    return to_chat_messages(messages[-limit:])


def _resolve_prior_email_draft(
    *,
    prior_results: dict[str, SubtaskResult] | None,
) -> dict[str, Any] | None:
    if prior_results:
        for pr in prior_results.values():
            draft_data = pr.get("data") or {}
            if draft_data.get("body") and draft_data.get("status") in {None, "draft", "sent"}:
                if draft_data.get("status") == "sent":
                    continue
                return {
                    "to": draft_data.get("to") or "",
                    "subject": draft_data.get("subject") or "",
                    "body": draft_data.get("body") or "",
                    "tone": draft_data.get("tone") or "professional",
                    "status": "draft",
                }
    from orchestrator.context import current_conversation_id

    conv_id = current_conversation_id.get() or ""
    if not conv_id:
        return None
    pending = DraftStore().get_pending_email(conv_id)
    if not pending or not pending.get("body"):
        return None
    return {
        "to": pending.get("to") or "",
        "subject": pending.get("subject") or "",
        "body": pending.get("body") or "",
        "tone": pending.get("tone") or "professional",
        "status": "draft",
    }


def _persist_email_hire_result(data: dict[str, Any] | None) -> None:
    if not data or not data.get("body"):
        return
    from orchestrator.context import current_conversation_id

    conv_id = current_conversation_id.get() or ""
    if not conv_id:
        return
    status = str(data.get("status") or "")
    if status == "draft":
        DraftStore().save_email_draft(
            conv_id,
            {
                "to": data.get("to") or "",
                "subject": data.get("subject") or "",
                "body": data.get("body") or "",
                "tone": data.get("tone") or "professional",
            },
        )
    elif status == "sent":
        mark_email_draft_sent(conv_id)


def _proposal_draft_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": data.get("title") or "",
        "subtitle": data.get("subtitle") or "",
        "client": data.get("client") or "",
        "tone": data.get("tone") or "professional",
        "sections": data.get("sections") or [],
        "closing": data.get("closing") or "",
        "format_notes": data.get("format_notes") or "",
        "document_id": data.get("document_id"),
        "url": data.get("url") or "",
        "status": data.get("status") or "draft",
    }


def _resolve_prior_proposal_draft(
    *,
    prior_results: dict[str, SubtaskResult] | None,
) -> dict[str, Any] | None:
    """Pass prior proposal IR (title/sections/document_id) into revise hires."""
    if prior_results:
        for pr in prior_results.values():
            data = pr.get("data") or {}
            if not (data.get("title") or data.get("sections") or data.get("document_id")):
                continue
            if str(data.get("status") or "") == "failed":
                continue
            return _proposal_draft_payload(data)

    from orchestrator.context import current_conversation_id

    conv_id = current_conversation_id.get() or ""
    if not conv_id:
        return None
    pending = DraftStore().get_proposal_draft(conv_id)
    if not pending or not pending.get("document_id"):
        return None
    return _proposal_draft_payload(pending)


def _persist_proposal_hire_result(data: dict[str, Any] | None) -> None:
    if not data:
        return
    if not (data.get("document_id") or data.get("title") or data.get("sections")):
        return
    status = str(data.get("status") or "")
    if status == "failed":
        return
    from orchestrator.context import current_conversation_id

    conv_id = current_conversation_id.get() or ""
    if not conv_id:
        return
    DraftStore().save_proposal_draft(conv_id, _proposal_draft_payload(data))


def _persist_document_hire_result(data: dict[str, Any] | None) -> None:
    if not data:
        return
    document_id = str(data.get("document_id") or "").strip()
    if not document_id or str(data.get("status") or "") == "failed":
        return
    from orchestrator.context import current_conversation_id

    conv_id = current_conversation_id.get() or ""
    if not conv_id:
        return
    title = str(data.get("title") or data.get("name") or "Google Doc")
    url = str(data.get("url") or "").strip()
    if not url:
        url = f"https://docs.google.com/document/d/{document_id}/edit"
    DraftStore().save_document_draft(
        conv_id,
        {
            "title": title,
            "document_id": document_id,
            "url": url,
            "status": data.get("status") or "created",
        },
    )


def _document_event_fields(data: dict[str, Any] | None) -> dict[str, str]:
    """Structured Doc fields for SSE so the chat UI can open the workspace pane."""
    if not data:
        return {}
    document_id = str(data.get("document_id") or "").strip()
    if not document_id:
        return {}
    url = str(data.get("url") or "").strip()
    if not url:
        url = f"https://docs.google.com/document/d/{document_id}/edit"
    title = str(data.get("title") or data.get("name") or "Google Doc").strip()
    return {
        "document_id": document_id,
        "document_url": url,
        "document_title": title or "Google Doc",
    }


# --- Validation stage ---------------------------------------------------------
# Validator agents are regular marketplace agents whose skill ends in
# "-validation" (link-validation, fact-validation, …). After execution the
# orchestrator ALWAYS validates results before they reach the user: planned
# validators first, then any online validator agents, and an LLM self-check
# when no validator agents are registered. Issues trigger one correction round
# re-hiring the responsible agent.

_VALIDATION_SKILL_SUFFIX = "-validation"
_SELF_VALIDATOR_ID = "self-validation"
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")


def _hire_skill_of(subtask: Subtask) -> str | None:
    tool = str(subtask.get("tool") or "")
    if tool.startswith("hire:"):
        return tool.split(":", 1)[1]
    return subtask.get("skill") or None


def _is_validator_skill(skill: str | None) -> bool:
    return bool(skill and skill.strip().lower().endswith(_VALIDATION_SKILL_SUFFIX))


def _is_validator_subtask(subtask: Subtask) -> bool:
    return _is_validator_skill(_hire_skill_of(subtask))


def _catalog_validators(catalog_agents: list) -> list[tuple[Any, str]]:
    """Online (agent, validator-skill) pairs from the marketplace catalog."""
    pairs: list[tuple[Any, str]] = []
    seen: set[str] = set()
    for agent in catalog_agents or []:
        if not getattr(agent, "online", False):
            continue
        for agent_skill in getattr(agent, "skills", []) or []:
            slug = (agent_skill.id or agent_skill.name or "").strip().lower()
            if _is_validator_skill(slug) and slug not in seen:
                seen.add(slug)
                pairs.append((agent, slug))
    return pairs


def _validation_issue_data(result: SubtaskResult | None) -> dict[str, Any] | None:
    """Validator contract: data.status == 'issues_found' means correction needed."""
    if not result or result.get("status") == "failed":
        return None
    data = result.get("data") or {}
    if data.get("status") == "issues_found":
        return data
    return None


def _find_planned_validation_issue(
    subtasks: list[Subtask],
    results_by_id: dict[str, SubtaskResult],
) -> tuple[Subtask, dict[str, Any]] | None:
    for subtask in subtasks:
        if not _is_validator_subtask(subtask):
            continue
        data = _validation_issue_data(results_by_id.get(subtask["id"]))
        if data:
            return subtask, data
    return None


def _find_responsible_subtask(
    subtasks: list[Subtask],
    results_by_id: dict[str, SubtaskResult],
    *,
    validator_id: str | None = None,
    validator_deps: list[str] | None = None,
) -> Subtask | None:
    """The subtask whose output should be corrected — validator deps first, then hires."""

    def has_result(subtask: Subtask) -> bool:
        if _is_validator_subtask(subtask) or subtask["id"] == validator_id:
            return False
        result = results_by_id.get(subtask["id"])
        return bool(result and result.get("status") != "failed")

    for dep_id in validator_deps or []:
        for subtask in subtasks:
            if subtask["id"] == dep_id and has_result(subtask):
                return subtask

    hires = [s for s in subtasks if has_result(s) and str(s.get("tool") or "").startswith("hire:")]
    if hires:
        return hires[-1]

    others = [s for s in subtasks if has_result(s)]
    return others[-1] if others else None


def _result_output_text(result: SubtaskResult, *, limit: int = 4000) -> str:
    """Text + any URLs from a result's data, for validators to inspect."""
    parts = [str(result.get("text") or "")]
    data = result.get("data") or {}
    for key in ("summary", "body"):
        value = str(data.get(key) or "")
        if value and value not in parts[0]:
            parts.append(value)
    urls: list[str] = []
    for source in data.get("sources") or []:
        if isinstance(source, dict) and source.get("url"):
            urls.append(str(source["url"]))
    combined = "\n\n".join(p for p in parts if p)
    for match in _URL_RE.finditer(combined):
        url = match.group(0).rstrip(".,;)'\"")
        if url not in urls:
            urls.append(url)
    if urls:
        combined += "\n\nLinks in this output:\n" + "\n".join(f"- {u}" for u in urls)
    return combined[:limit]


class SelfValidation(BaseModel):
    status: Literal["ok", "issues_found"] = Field(
        description="ok when the output is fit to deliver; issues_found for clear problems"
    )
    issues: str = Field(default="", description="Short description of the problems found")
    correction_request: str = Field(
        default="",
        description="Actionable instruction for the responsible agent to fix its output",
    )


async def _self_validate(query: str, output_text: str) -> dict[str, Any]:
    """Orchestrator's own validation when no validator agents are registered."""
    llm = get_structured_llm(SelfValidation, temperature=0)
    try:
        decision: SelfValidation = await llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You are the orchestrator's output validator — the last check before "
                        "a result is delivered to the user. Verify that the output actually "
                        "addresses the user's request, is internally consistent, contains no "
                        "raw HTML dumps or broken formatting, and claims no success that the "
                        "results do not support. Only report issues_found for CLEAR problems "
                        "that require redoing the work — do not nitpick style or tone. "
                        "When issues are found, write a correction_request telling the "
                        "responsible agent exactly what is wrong and what to re-deliver."
                    ),
                },
                {
                    "role": "user",
                    "content": f"User request:\n{query}\n\nOutput to validate:\n{output_text}",
                },
            ]
        )  # type: ignore[assignment]
    except Exception:
        return {"status": "ok", "issues": "", "correction_request": ""}
    return {
        "status": decision.status,
        "issues": decision.issues,
        "correction_request": decision.correction_request,
    }


async def _run_self_validation(query: str, output_text: str) -> dict[str, Any]:
    """Self-validation with subtask events so the session UI shows the check."""
    emit(
        "subtask_start",
        id=_SELF_VALIDATOR_ID,
        title="Validate output (orchestrator)",
        assignee="orchestrator",
        skill=None,
        tool="validate:self",
        instruction="No validator agents registered — orchestrator validates the output itself.",
    )
    data = await _self_validate(query, output_text)
    emit(
        "subtask_done",
        id=_SELF_VALIDATOR_ID,
        status="completed",
        assignee="orchestrator",
        text=(
            "Output looks good — delivering."
            if data.get("status") == "ok"
            else f"Issues found: {data.get('issues', '')}"[:500]
        ),
    )
    return data


async def _run_validation_stage(
    subtasks: list[Subtask],
    results_by_id: dict[str, SubtaskResult],
    all_results: list[SubtaskResult],
    manager: CognilanceManager,
    router: ToolRouter,
    *,
    catalog_agents: list,
    query: str,
    conversation: list[BaseMessage] | None,
) -> list[SubtaskResult]:
    """Validate only when the plan includes a *-validation skill (opt-in)."""
    worker_subtasks = [s for s in subtasks if not _is_validator_subtask(s)]
    worker_ok = [
        results_by_id[s["id"]]
        for s in worker_subtasks
        if results_by_id.get(s["id"]) and results_by_id[s["id"]].get("status") != "failed"
    ]
    if not worker_ok:
        return all_results

    planned_skills = {
        skill for s in subtasks if _is_validator_skill(skill := _hire_skill_of(s)) and skill
    }
    # No automatic self-validation or unsolicited validator hires.
    if not planned_skills:
        return all_results

    validator_subtask: Subtask | None = None
    validation_data: dict[str, Any] | None = None
    self_validated = False

    planned_issue = _find_planned_validation_issue(subtasks, results_by_id)
    if planned_issue:
        validator_subtask, validation_data = planned_issue

    if not validation_data:
        return all_results

    responsible = _find_responsible_subtask(
        subtasks,
        results_by_id,
        validator_id=validator_subtask["id"] if validator_subtask else _SELF_VALIDATOR_ID,
        validator_deps=(validator_subtask or {}).get("depends_on"),
    )
    if not responsible:
        return all_results

    return await _apply_correction(
        responsible,
        validator_subtask,
        validation_data,
        results_by_id,
        all_results,
        manager,
        router,
        conversation=conversation,
        query=query,
        self_validated=self_validated,
    )


async def _apply_correction(
    responsible: Subtask,
    validator_subtask: Subtask | None,
    validation_data: dict[str, Any],
    results_by_id: dict[str, SubtaskResult],
    all_results: list[SubtaskResult],
    manager: CognilanceManager,
    router: ToolRouter,
    *,
    conversation: list[BaseMessage] | None,
    query: str,
    self_validated: bool,
) -> list[SubtaskResult]:
    """One correction round: re-run the responsible subtask, then re-validate."""
    correction_request = str(validation_data.get("correction_request") or "").strip()
    if not correction_request:
        issues = str(validation_data.get("issues") or "").strip()
        broken = [str(u) for u in validation_data.get("broken_links") or []]
        details = issues or ("Broken links:\n" + "\n".join(f"- {u}" for u in broken) if broken else "")
        if not details:
            return all_results
        correction_request = f"Fix these problems and re-deliver your output:\n{details}"

    validator_name = (
        (validator_subtask or {}).get("assignee") if validator_subtask else "orchestrator"
    )
    responsible_result = results_by_id.get(responsible["id"]) or {}
    emit_status(
        f"Validation found issues — re-running {responsible.get('assignee') or 'the responsible agent'}…"
    )
    emit(
        "correction_start",
        responsible=responsible.get("assignee"),
        validator=validator_name,
        request=correction_request[:500],
    )

    fix_subtask: Subtask = {
        **responsible,
        "id": f"{responsible['id']}-fix",
        "title": f"Fix issues: {responsible.get('title') or responsible['id']}",
        "instruction": (
            f"{responsible.get('instruction') or ''}\n\n"
            "CORRECTION REQUIRED — a validator checked your previous output and found "
            "problems. Fix them and re-deliver your full output:\n"
            f"{correction_request}\n\n"
            f"Your previous output:\n{(responsible_result.get('text') or '')[:2000]}"
        ),
        "depends_on": [],
    }
    fix_result = await _run_subtask(
        fix_subtask, manager, router, conversation=conversation, prior_results=results_by_id
    )
    results_by_id[fix_subtask["id"]] = fix_result
    if fix_result.get("status") == "failed":
        emit("correction_done", status="failed")
        return all_results

    updated = [
        fix_result if r.get("subtask_id") == responsible["id"] else r for r in all_results
    ]
    corrected_text = _result_output_text(fix_result)

    if self_validated or validator_subtask is None:
        recheck = await _self_validate(query, corrected_text)
        emit("correction_done", status=str(recheck.get("status") or "unknown"))
        return updated

    recheck_subtask: Subtask = {
        **validator_subtask,
        "id": f"{validator_subtask['id']}-recheck",
        "title": "Re-validate corrected output",
        "instruction": (
            "Validate this corrected output before it is delivered to the user:\n\n"
            f"{corrected_text}"
        ),
        "depends_on": [],
    }
    recheck_result = await _run_subtask(
        recheck_subtask, manager, router, conversation=conversation, prior_results=results_by_id
    )
    results_by_id[recheck_subtask["id"]] = recheck_result
    updated = [
        recheck_result if r.get("subtask_id") == validator_subtask["id"] else r for r in updated
    ]
    emit(
        "correction_done",
        status=str((recheck_result.get("data") or {}).get("status") or "unknown"),
    )
    return updated


def _dependency_layers(subtasks: list[Subtask]) -> list[list[Subtask]]:
    """Topological sort into layers for parallel execution."""
    if not subtasks:
        return []

    by_id = {item["id"]: item for item in subtasks}
    indegree: dict[str, int] = {item["id"]: 0 for item in subtasks}
    dependents: dict[str, list[str]] = defaultdict(list)

    for item in subtasks:
        for dep in item.get("depends_on") or []:
            if dep not in by_id:
                continue
            indegree[item["id"]] += 1
            dependents[dep].append(item["id"])

    layers: list[list[Subtask]] = []
    ready = deque([sid for sid, degree in indegree.items() if degree == 0])

    while ready:
        layer_ids = list(ready)
        ready.clear()
        layer = [by_id[sid] for sid in layer_ids]
        layers.append(layer)
        for sid in layer_ids:
            for child in dependents[sid]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)

    remaining = [sid for sid, degree in indegree.items() if degree > 0]
    if remaining:
        seen = {item["id"] for layer in layers for item in layer}
        layers.append([by_id[sid] for sid in remaining if sid in by_id and sid not in seen])

    return layers


async def _run_subtask(
    subtask: Subtask,
    manager: CognilanceManager,
    router: ToolRouter,
    *,
    conversation: list[BaseMessage] | None = None,
    prior_results: dict[str, SubtaskResult] | None = None,
) -> SubtaskResult:
    subtask_id = subtask["id"]
    instruction = subtask.get("instruction") or ""
    if prior_results:
        for dep_id in subtask.get("depends_on") or []:
            prior = prior_results.get(dep_id)
            if prior and prior.get("text"):
                instruction = f"{instruction}\n\nContext from prior step:\n{prior['text']}"
    skill = subtask.get("skill")
    tool = subtask.get("tool")
    assignee = subtask.get("assignee") or "thinking"

    emit(
        "subtask_start",
        id=subtask_id,
        title=subtask.get("title", ""),
        assignee=assignee,
        skill=skill,
        tool=tool or (f"hire:{skill}" if skill else "thinking"),
        instruction=instruction,
    )
    emit_status(f"Running: {subtask.get('title', subtask_id)}")

    try:
        extra_input: dict[str, Any] = {
            "action": subtask.get("action"),
            "params": subtask.get("params"),
            "conversation": conversation,
            "conversation_history": _conversation_history(conversation),
            "plan_context": subtask.get("plan_context") or "",
            "subtask_id": subtask_id,
        }
        hire_skill = skill
        if not hire_skill and tool and str(tool).startswith("hire:"):
            hire_skill = str(tool).split(":", 1)[1]
        if hire_skill == "email-writing":
            prior_draft = _resolve_prior_email_draft(prior_results=prior_results)
            if prior_draft:
                extra_input["prior_draft"] = prior_draft
        if hire_skill == "proposal-writing":
            prior_proposal = _resolve_prior_proposal_draft(prior_results=prior_results)
            if prior_proposal:
                extra_input["prior_draft"] = prior_proposal
        result = await router.execute(
            manager,
            tool=tool,
            skill=skill,
            instruction=instruction,
            input_data=extra_input,
        )
        if hire_skill == "email-writing" and result.status != "failed":
            _persist_email_hire_result(result.data)
        if hire_skill == "proposal-writing" and result.status != "failed":
            _persist_proposal_hire_result(result.data)
        if hire_skill == "docs-creating" and result.status != "failed":
            _persist_document_hire_result(result.data)
        payload: SubtaskResult = {
            "subtask_id": subtask_id,
            "text": result.text,
            "data": result.data,
            "assignee": result.assignee,
            "status": result.status,
        }
        emit(
            "subtask_done",
            id=subtask_id,
            status=result.status,
            assignee=result.assignee,
            text=(result.text or "")[:500],
            **_document_event_fields(result.data if isinstance(result.data, dict) else None),
        )
        return payload
    except Exception as exc:
        payload = {
            "subtask_id": subtask_id,
            "text": str(exc),
            "data": {},
            "assignee": assignee,
            "status": "failed",
        }
        emit(
            "subtask_done",
            id=subtask_id,
            status="failed",
            assignee=assignee,
            text=str(exc)[:500],
        )
        return payload


def _merge_data(results: list[SubtaskResult]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for result in results:
        data = result.get("data") or {}
        for key, value in data.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key] = merged[key] + value
            elif key == "body":
                continue
            else:
                merged[key] = value
    # Prefer last result that carries a document_id for the active Doc workspace.
    for result in reversed(results):
        data = result.get("data") or {}
        if data.get("document_id"):
            merged["document_id"] = data["document_id"]
            if data.get("url"):
                merged["url"] = data["url"]
            if data.get("title") or data.get("name"):
                merged["title"] = data.get("title") or data.get("name")
            break
    return merged


def _result_facts(results: list[SubtaskResult]) -> str:
    parts: list[str] = []
    for result in results:
        if result.get("status") == "failed":
            parts.append(f"FAILED ({result.get('assignee', 'agent')}): {result.get('text', '')}")
            continue
        data = result.get("data") or {}
        if data.get("emails"):
            parts.append(format_gmail_list_result(data))
        elif data.get("events") is not None:
            parts.append(format_calendar_list_result(data))
        elif data.get("sources") and data.get("query"):
            parts.append(format_web_search_result(data))
        elif data.get("url") and data.get("content") is not None:
            parts.append(format_web_fetch_result(data))
        elif data.get("draft") or (data.get("status") == "draft" and data.get("body")):
            parts.append(format_email_draft(data))
        elif data.get("gmail_message_id") or data.get("status") == "sent" or (
            data.get("id") and data.get("sent_body")
        ):
            parts.append(format_send_email_result(data))
        elif data.get("document_id") or data.get("status") in {
            "published",
            "preview",
            "already_applied",
            "applied",
        } or str(data.get("url", "")).startswith("https://docs.google.com/document/"):
            parts.append(format_document_result(data))
        elif data.get("subscription_id") or "stopped" in data:
            if data.get("kind") == "recurring_task" or data.get("instruction"):
                parts.append(format_recurring_result(data))
            else:
                parts.append(format_subscription_result(data))
        elif result.get("text"):
            parts.append(f"[{result.get('assignee', 'agent')}] {result.get('text')}")
    return "\n\n".join(parts).strip()


async def _synthesize_final(
    query: str,
    results: list[SubtaskResult],
    *,
    conversation: list[BaseMessage] | None = None,
) -> tuple[str, bool]:
    """Return (final_text, answer_streamed)."""
    if not results:
        return "", False

    if len(results) == 1 and results[0].get("status") == "failed":
        return results[0].get("text") or "The task failed.", False

    facts = _result_facts(results)
    if not facts:
        return (results[0].get("text") or "" if len(results) == 1 else ""), False

    if len(results) == 1:
        data = results[0].get("data") or {}
        if data.get("draft") or (data.get("status") == "draft" and data.get("body")):
            return format_email_draft(data), False
        if data.get("gmail_message_id") or data.get("status") == "sent" or (
            data.get("id") and data.get("sent_body")
        ):
            return format_send_email_result(data), False
        # Style/alignment replies must not be rephrased into "created a Doc".
        if data.get("status") in {"already_applied", "applied"} or (
            data.get("alignment") and data.get("message")
        ):
            return format_document_result(data), False
        # Empty titled Docs: keep the agent's "Created empty…" line, no invented body.
        if data.get("status") == "created":
            return format_document_result(data), False
        if data.get("subscription_id") or "stopped" in data:
            if data.get("kind") == "recurring_task" or data.get("instruction"):
                return format_recurring_result(data), False
            return format_subscription_result(data), False
        if data.get("sources") and data.get("query"):
            return format_web_search_result(data), False
        if data.get("url") and data.get("content") is not None and results[0].get("assignee") == "web":
            return format_web_fetch_result(data), False

    llm = get_llm(temperature=0.3)
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are Cognilance replying in chat. "
                "Write a short, natural answer using the execution results below, "
                "formatted as clean Markdown (bold, lists, links) — the chat renders Markdown. "
                "NEVER output raw HTML tags or inline CSS; if results contain HTML "
                "(e.g. an email body), summarize it in plain language instead of echoing it — "
                "a rich card below your message shows the full content. "
                "Preserve links, counts, and facts exactly. "
                "Never mention tools, APIs, subscribe_inbox, or internal orchestration. "
                "Never claim an action succeeded if results say FAILED. "
                "Never claim an email was sent unless execution results include a Gmail message ID. "
                "One to three sentences unless listing emails, documents, or sources."
            ),
        },
    ]
    if conversation:
        messages.extend(to_chat_messages(conversation))
    messages.append(
        {
            "role": "user",
            "content": f"User request:\n{query}\n\nExecution results:\n{facts}",
        }
    )
    try:
        text = await stream_llm(llm, messages, event="answer")
        if text.strip():
            emit("answer_done", text=text)
            return text, True
        return facts, False
    except Exception:
        return facts, False


async def task_agent(state: State) -> dict:
    from orchestrator.registry_cache import deserialize_agents

    subtasks = state.get("subtasks") or []
    query = last_user_text(state.get("messages", []))
    emit("execution_start")

    if not subtasks:
        emit("execution_done")
        return {"subtask_results": [], "final_text": "", "final_data": {}}

    catalog_agents = deserialize_agents(state.get("catalog_agents") or [])
    router = ToolRouter(catalog_agents=catalog_agents, integration_client=IntegrationClient())
    layers = _dependency_layers(subtasks)
    all_results: list[SubtaskResult] = []
    plan_context = str((state.get("thinking") or "")).strip()

    async with CognilanceManager(agent_name="Orchestrator") as manager:
        results_by_id: dict[str, SubtaskResult] = {}
        for layer in layers:
            layer_results = await asyncio.gather(
                *[
                    _run_subtask(
                        {
                            **item,
                            "plan_context": item.get("plan_context") or plan_context,
                        },
                        manager,
                        router,
                        conversation=state.get("messages", []),
                        prior_results=results_by_id,
                    )
                    for item in layer
                ]
            )
            for item, result in zip(layer, layer_results):
                results_by_id[item["id"]] = result
            all_results.extend(layer_results)

        all_results = await _run_validation_stage(
            subtasks,
            results_by_id,
            all_results,
            manager,
            router,
            catalog_agents=catalog_agents,
            query=query,
            conversation=state.get("messages", []),
        )

    emit_status("Aggregating results…")
    final_text, answer_streamed = await _synthesize_final(
        query,
        all_results,
        conversation=state.get("messages", []),
    )
    final_data = _merge_data(all_results)
    emit("execution_done")

    return {
        "subtask_results": all_results,
        "final_text": final_text,
        "final_data": final_data,
        "answer_streamed": answer_streamed,
    }
