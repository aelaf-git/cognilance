"""Specialist nodes: claim board tasks and execute via a multi-step agent loop."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage

from agents.loader import SPECIALISTS, RolePack, get_role
from core.context.request import current_mission_id
from core.models.gateway import get_structured_llm, to_chat_messages
from core.runtime.board.store import BoardStore
from core.runtime.runs.models import RunStatus
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.schema import SpecialistAction
from pipelines.coordinator_board.verify import verify_task_output
from pipelines.shared.state import State, SubtaskResult
from pipelines.shared.streaming import emit, emit_status, reveal_text
from tools.registry import ApprovalRequired, is_allowed, load_manifests, run_role_tool

MAX_LOOP_STEPS = 5
MAX_CONVERSATION_MESSAGES = 10
MAX_OBSERVATION_CHARS = 4000


def _run_id(state: State) -> str:
    return str(state.get("run_id") or current_mission_id.get() or "").strip()


def _pick_tool(role_id: str, instruction: str, allowed: tuple[str, ...] = ()) -> str:
    """Cheap heuristic tool choice, constrained to the role's manifest tool list."""
    text = instruction.lower()

    def first(*candidates: str) -> str:
        for c in candidates:
            if not allowed or c in allowed:
                return c
        return "thinking"

    if role_id == "researcher":
        if ("http://" in text or "https://" in text) and "valid" in text:
            return first("link_validate.check")
        # Default to thinking (greetings / chitchat / pure Q&A). Only search
        # when the instruction clearly asks for web research.
        research_intent = (
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
        if any(w in text for w in research_intent):
            return first("web.search")
        return "thinking"
    if role_id == "email_agent":
        if any(w in text for w in ("send it", "ship it", "send the email", "send now")):
            return first("gmail.send", "gmail.draft")
        return first("gmail.draft")
    if role_id == "x_agent":
        if any(
            w in text
            for w in ("post it", "publish", "tweet it", "send it", "post now", "publish it")
        ):
            return first("x.post", "x.draft")
        return first("x.draft")
    if role_id == "reddit_agent":
        if any(
            w in text
            for w in ("post it", "publish", "submit it", "send it", "post now", "publish it")
        ):
            return first("reddit.post", "reddit.draft")
        return first("reddit.draft")
    if role_id == "linkedin_agent":
        if any(
            w in text
            for w in ("post it", "publish", "send it", "post now", "publish it")
        ):
            return first("linkedin.post", "linkedin.draft")
        return first("linkedin.draft")
    if role_id in {"report_writer", "concept_note_writer"}:
        if "doc" in text or "proposal" in text or "google" in text or "concept note" in text:
            return first("google_docs.create")
        return "thinking"
    return "thinking"


def _tool_blurb(tool_id: str) -> str:
    if tool_id == "thinking":
        return "Answer or reason directly without external APIs"
    base, _, action = tool_id.partition(".")
    manifest = load_manifests().get(base)
    if not manifest:
        return tool_id
    action_spec = manifest.actions.get(action) or {}
    desc = str(action_spec.get("description") or "").strip()
    if desc:
        return desc
    return str(manifest.description or tool_id)


def _allowed_tools_blurb(pack: RolePack) -> str:
    ids = list(pack.tools)
    if "thinking" not in ids:
        ids = ["thinking", *ids]
    return "\n".join(f"- {tid}: {_tool_blurb(tid)}" for tid in ids)


def _conversation_snippet(messages: list[BaseMessage] | None) -> str:
    rows = to_chat_messages(messages or [])[-MAX_CONVERSATION_MESSAGES:]
    if not rows:
        return "(no prior conversation)"
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


def _observations_block(observations: list[dict[str, str]]) -> str:
    if not observations:
        return "(none yet)"
    parts: list[str] = []
    for i, obs in enumerate(observations, 1):
        text = (obs.get("text") or "")[:MAX_OBSERVATION_CHARS]
        parts.append(f"Step {i} [{obs.get('tool')}]:\n{text}")
    return "\n\n".join(parts)


def _decision_prompt(
    pack: RolePack,
    *,
    instruction: str,
    messages: list[BaseMessage] | None,
    observations: list[dict[str, str]],
) -> str:
    role_rules = (pack.prompt("system") or pack.instructions or "").strip()
    return (
        f"You are the {pack.name} specialist completing one board task.\n"
        f"{role_rules}\n\n"
        "Decide the next action. Prefer call_tool when external info or an integration "
        "action is needed; set status=done with a clear answer when finished.\n"
        "Use only the listed tools. Put focused queries in tool_instruction.\n"
        "Do not mention tools, roles, or orchestration in answer.\n\n"
        f"Allowed tools:\n{_allowed_tools_blurb(pack)}\n\n"
        f"Task instruction:\n{instruction}\n\n"
        f"Recent conversation:\n{_conversation_snippet(messages)}\n\n"
        f"Observations so far:\n{_observations_block(observations)}\n"
    )


def _normalize_tool(pack: RolePack, tool: str) -> str:
    tool_id = (tool or "thinking").strip() or "thinking"
    if tool_id == "thinking" or is_allowed(pack.tools, tool_id):
        return tool_id
    return "thinking"


async def _fallback_once(
    pack: RolePack,
    instruction: str,
    conversation: list[BaseMessage] | None,
) -> dict[str, Any]:
    tool = _pick_tool(pack.id, instruction, pack.tools)
    return await run_role_tool(
        pack,
        tool,
        instruction=instruction,
        conversation=conversation,
    )


async def _run_task_loop(
    pack: RolePack,
    *,
    instruction: str,
    messages: list[BaseMessage] | None,
) -> dict[str, Any]:
    """Observe→act loop for one board task. Raises ApprovalRequired unchanged."""
    observations: list[dict[str, str]] = []
    merged_data: dict[str, Any] = {}
    last_tool = "thinking"
    last_risk: str | None = None
    conversation = list(messages or [])

    for _ in range(MAX_LOOP_STEPS):
        try:
            llm = get_structured_llm(SpecialistAction, temperature=0.1)
            action: SpecialistAction = await llm.ainvoke(
                _decision_prompt(
                    pack,
                    instruction=instruction,
                    messages=conversation,
                    observations=observations,
                )
            )
        except Exception:
            if observations:
                text = observations[-1].get("text") or ""
                return {
                    "text": text,
                    "data": merged_data,
                    "tool": last_tool,
                    "risk": last_risk,
                }
            out = await _fallback_once(pack, instruction, conversation)
            return {
                "text": str(out.get("text") or ""),
                "data": dict(out.get("data") or {}),
                "tool": _pick_tool(pack.id, instruction, pack.tools),
                "risk": out.get("risk"),
            }

        if action.reasoning:
            reveal_text(action.reasoning, event="thinking")

        if action.status == "done":
            answer = (action.answer or "").strip()
            if not answer and observations:
                answer = observations[-1].get("text") or ""
            if not answer:
                out = await _fallback_once(pack, instruction, conversation)
                return {
                    "text": str(out.get("text") or ""),
                    "data": dict(out.get("data") or {}),
                    "tool": "thinking",
                    "risk": out.get("risk"),
                }
            return {
                "text": answer,
                "data": merged_data,
                "tool": last_tool,
                "risk": last_risk,
            }

        tool = _normalize_tool(pack, action.tool)
        tool_instruction = (action.tool_instruction or instruction).strip() or instruction
        out = await run_role_tool(
            pack,
            tool,
            instruction=tool_instruction,
            conversation=conversation,
        )
        text = str(out.get("text") or "")
        data = dict(out.get("data") or {})
        last_tool = tool
        last_risk = out.get("risk")
        for k, v in data.items():
            if k not in merged_data or merged_data[k] in (None, "", [], {}):
                merged_data[k] = v
            elif isinstance(merged_data[k], list) and isinstance(v, list):
                merged_data[k] = merged_data[k] + v
        observations.append({"tool": tool, "text": text})

    # Max steps: synthesize from last observation or ask the model once more for done.
    if observations:
        try:
            llm = get_structured_llm(SpecialistAction, temperature=0.1)
            action = await llm.ainvoke(
                _decision_prompt(
                    pack,
                    instruction=instruction,
                    messages=conversation,
                    observations=observations,
                )
                + "\nYou have reached the step limit. Respond with status=done and a final answer.\n"
            )
            answer = (action.answer or "").strip() or observations[-1].get("text") or ""
            return {
                "text": answer,
                "data": merged_data,
                "tool": last_tool,
                "risk": last_risk,
            }
        except Exception:
            return {
                "text": observations[-1].get("text") or "",
                "data": merged_data,
                "tool": last_tool,
                "risk": last_risk,
            }

    out = await _fallback_once(pack, instruction, conversation)
    return {
        "text": str(out.get("text") or ""),
        "data": dict(out.get("data") or {}),
        "tool": _pick_tool(pack.id, instruction, pack.tools),
        "risk": out.get("risk"),
    }


async def _run_specialist(state: State, role_id: str) -> dict[str, Any]:
    pack = get_role(role_id)
    if pack is None:
        return {}
    emit_status(f"{pack.name} working…")
    emit("specialist_start", role=role_id, name=pack.name)

    run_id = _run_id(state)
    board = BoardStore()
    board.init_db()
    runs = RunStore()
    runs.init_db()

    results: list[SubtaskResult] = list(state.get("subtask_results") or [])
    pending_approval = None
    waiting = False
    needs_clarification = False
    clarification: dict[str, Any] | None = None
    messages = list(state.get("messages") or [])

    tasks = []
    if run_id:
        tasks = board.claim_open_for_role(run_id, role_id)
        for t in tasks:
            runs.append_step(
                run_id,
                kind="task_claimed",
                text=t.title,
                data={"task_id": t.id, "role": role_id},
            )
    else:
        # In-memory board from state
        for raw in state.get("board_tasks") or []:
            if raw.get("assignee_role") == role_id and raw.get("status", "open") == "open":
                tasks.append(raw)  # type: ignore[arg-type]

    if not tasks:
        emit("specialist_done", role=role_id, tasks=0)
        return {}

    for task in tasks:
        if hasattr(task, "id"):
            task_id = task.id
            instruction = task.instruction
            title = task.title
        else:
            task_id = str(task.get("id"))
            instruction = str(task.get("instruction") or "")
            title = str(task.get("title") or "")

        try:
            out = await _run_task_loop(pack, instruction=instruction, messages=messages)
            text = str(out.get("text") or "")
            data = dict(out.get("data") or {})

            verdict = await verify_task_output(
                pack,
                instruction=instruction,
                text=text,
                data=data,
            )
            if run_id:
                runs.append_step(
                    run_id,
                    kind="verify",
                    text=title,
                    data={
                        "task_id": task_id,
                        "passed": verdict.passed,
                        "issues": list(verdict.issues),
                        "questions": list(verdict.clarifying_questions),
                        "reasoning": verdict.reasoning,
                    },
                )

            if not verdict.passed:
                fail_data = {
                    **data,
                    "verification": {
                        "passed": False,
                        "issues": list(verdict.issues),
                        "questions": list(verdict.clarifying_questions),
                        "reasoning": verdict.reasoning,
                    },
                }
                if run_id:
                    board.complete_task(
                        task_id,
                        result_text=text,
                        result_json=fail_data,
                        failed=True,
                    )
                needs_clarification = True
                clarification = {
                    "task_id": task_id,
                    "role": role_id,
                    "title": title,
                    "issues": list(verdict.issues),
                    "questions": list(verdict.clarifying_questions),
                }
                emit(
                    "clarification_required",
                    task_id=task_id,
                    role=role_id,
                    issues=clarification["issues"],
                    questions=clarification["questions"],
                )
                break

            if run_id:
                board.complete_task(task_id, result_text=text, result_json=data)
                runs.append_step(
                    run_id,
                    kind="task_done",
                    text=title,
                    data={
                        "task_id": task_id,
                        "tool": out.get("tool"),
                        "risk": out.get("risk"),
                    },
                )
            results.append(
                {
                    "subtask_id": task_id,
                    "text": text,
                    "data": data,
                    "assignee": role_id,
                    "status": "completed",
                }
            )
        except ApprovalRequired as exc:
            waiting = True
            pending_approval = {
                "tool": exc.tool,
                "action": exc.action,
                "params": exc.params,
                "risk": exc.risk,
                "role": role_id,
                "task_id": task_id,
            }
            if run_id:
                runs.update_status(
                    run_id,
                    RunStatus.WAITING_APPROVAL,
                    pending_approval=pending_approval,
                )
                runs.append_step(
                    run_id,
                    kind="approval",
                    text=f"Approval required for {exc.tool}",
                    data=pending_approval,
                )
            emit("approval_required", **pending_approval)
            break
        except Exception as exc:
            err = str(exc)
            if run_id:
                board.complete_task(task_id, result_text=err, result_json={"error": err}, failed=True)
            results.append(
                {
                    "subtask_id": task_id,
                    "text": err,
                    "data": {"error": err},
                    "assignee": role_id,
                    "status": "failed",
                }
            )

    emit("specialist_done", role=role_id, tasks=len(tasks))
    update: dict[str, Any] = {"subtask_results": results}
    if waiting:
        update["waiting_approval"] = True
        update["pending_approval"] = pending_approval
    if needs_clarification:
        update["needs_clarification"] = True
        update["clarification"] = clarification
    return update


def specialist_node(role_id: str):
    """Build a graph node that runs one specialist (handy for custom pipelines)."""

    async def _node(state: State) -> dict[str, Any]:
        return await _run_specialist(state, role_id)

    _node.__name__ = f"{role_id}_node"
    return _node


async def specialists_fanout(state: State) -> dict[str, Any]:
    """Run all specialists sequentially in dependency layers (simple fan-out)."""
    merged: dict[str, Any] = {"subtask_results": list(state.get("subtask_results") or [])}
    # Up to 3 waves so depends_on can resolve.
    for _ in range(3):
        progress = False
        for role in SPECIALISTS:
            # Skip if waiting approval or clarification
            if (
                merged.get("waiting_approval")
                or state.get("waiting_approval")
                or merged.get("needs_clarification")
                or state.get("needs_clarification")
            ):
                break
            # Build a view state with latest results
            view: State = {**state, **merged}  # type: ignore[misc]
            update = await _run_specialist(view, role.id)
            if update:
                progress = True
                if update.get("subtask_results"):
                    # merge by id
                    by_id = {
                        str(r.get("subtask_id")): r
                        for r in merged.get("subtask_results") or []
                    }
                    for r in update["subtask_results"]:
                        by_id[str(r.get("subtask_id"))] = r
                    merged["subtask_results"] = list(by_id.values())
                if update.get("waiting_approval"):
                    merged["waiting_approval"] = True
                    merged["pending_approval"] = update.get("pending_approval")
                    break
                if update.get("needs_clarification"):
                    merged["needs_clarification"] = True
                    merged["clarification"] = update.get("clarification")
                    break
        if (
            not progress
            or merged.get("waiting_approval")
            or merged.get("needs_clarification")
        ):
            break
    return merged
