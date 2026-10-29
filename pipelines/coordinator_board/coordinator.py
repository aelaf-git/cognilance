"""Coordinator: plan board tasks, then assemble specialist results."""

from __future__ import annotations

import json
import uuid
from typing import Any

from langchain_core.messages import BaseMessage

from agents.coordinator.schema import CoordinatorPlan, PlannedTask
from agents.loader import SPECIALISTS, coordinator, normalize_role_id, specialist_ids
from core.context.request import current_mission_id
from core.models.gateway import get_llm, get_structured_llm, last_user_text, to_chat_messages
from core.runtime.board.store import BoardStore
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.verify import format_clarification_message
from pipelines.shared.state import BoardTaskState, State
from pipelines.shared.streaming import emit, emit_status, reveal_text

MAX_PLAN_THREAD_MESSAGES = 8


def _run_id(state: State) -> str:
    return str(state.get("run_id") or current_mission_id.get() or "").strip()


def _thread_snippet(messages: list[BaseMessage] | None, *, limit: int = MAX_PLAN_THREAD_MESSAGES) -> str:
    rows = to_chat_messages(messages or [])[-limit:]
    if not rows:
        return ""
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


def _plan_prompt(query: str, *, thread: str = "") -> str:
    pack = coordinator()
    roles_blurb = "\n".join(f"- {r.id}: {r.description or r.instructions}" for r in SPECIALISTS)
    header = pack.prompts.get("plan") or pack.instructions
    parts = [
        header.strip(),
        "",
        "Specialists:",
        roles_blurb,
        "",
        f"User request:\n{query}",
    ]
    if thread.strip():
        parts.extend(["", f"Recent conversation (for follow-ups; tasks must still be self-contained):\n{thread}"])
    return "\n".join(parts) + "\n"


def _validate_assignees(plan: CoordinatorPlan) -> CoordinatorPlan:
    """Normalise legacy ids and drop tasks for unknown specialists."""
    valid = set(specialist_ids())
    kept: list[PlannedTask] = []
    for task in plan.tasks:
        role = normalize_role_id(task.assignee_role)
        if role not in valid:
            emit("plan", text=f"Dropped task for unknown specialist: {task.assignee_role}")
            continue
        kept.append(task.model_copy(update={"assignee_role": role}))
    return plan.model_copy(update={"tasks": kept})


def _plan_from_preset(state: State) -> CoordinatorPlan | None:
    preset = state.get("preset_tasks") or []
    if not preset:
        return None
    id_to_title = {str(t.get("id")): str(t.get("title") or "") for t in preset}
    return CoordinatorPlan(
        reasoning=f"Preset pipeline: {state.get('pipeline') or 'custom'}",
        tasks=[
            PlannedTask(
                title=str(t.get("title") or ""),
                instruction=str(t.get("instruction") or ""),
                assignee_role=str(t.get("assignee_role") or ""),
                depends_on_titles=[id_to_title[d] for d in t.get("depends_on") or [] if d in id_to_title],
            )
            for t in preset
        ],
    )


async def coordinator_plan(state: State) -> dict[str, Any]:
    emit_status("Coordinator planning…")
    messages = state.get("messages") or []
    query = last_user_text(messages)
    thread = _thread_snippet(messages)

    plan = _plan_from_preset(state)
    if plan is None:
        llm = get_structured_llm(CoordinatorPlan, temperature=0.1)
        try:
            plan = await llm.ainvoke(_plan_prompt(query, thread=thread))
        except Exception as exc:
            emit("plan", text=f"Planner fallback: {exc}")
            plan = CoordinatorPlan(
                reasoning="fallback conversational reply",
                tasks=[],
                suggested_ui="text",
            )
    plan = _validate_assignees(plan)

    if not plan.tasks:
        plan = CoordinatorPlan(
            reasoning=plan.reasoning or "fallback conversational reply",
            tasks=[
                PlannedTask(
                    title="Reply",
                    instruction=(
                        "Reply to the user conversationally. Do not search the web. "
                        f"Their message: {query}"
                    ),
                    assignee_role="researcher",
                )
            ],
            suggested_ui=plan.suggested_ui or "text",
        )

    if plan.reasoning:
        reveal_text(plan.reasoning, event="thinking")

    run_id = _run_id(state)
    board = BoardStore()
    board.init_db()
    runs = RunStore()
    runs.init_db()

    title_to_id: dict[str, str] = {}
    board_tasks: list[BoardTaskState] = []
    for planned in plan.tasks:
        tid = str(uuid.uuid4())
        title_to_id[planned.title] = tid
        depends = [title_to_id[t] for t in planned.depends_on_titles if t in title_to_id]
        if run_id:
            task = board.create_task(
                run_id=run_id,
                title=planned.title,
                instruction=planned.instruction,
                assignee_role=planned.assignee_role,
                depends_on=depends,
                task_id=tid,
            )
            runs.append_step(
                run_id,
                kind="task_created",
                text=planned.title,
                data=task.to_dict(),
            )
            board_tasks.append(task.to_dict())  # type: ignore[arg-type]
        else:
            board_tasks.append(
                {
                    "id": tid,
                    "title": planned.title,
                    "instruction": planned.instruction,
                    "assignee_role": planned.assignee_role,
                    "status": "open",
                    "depends_on": depends,
                    "result_text": "",
                    "result_json": {},
                }
            )

    emit(
        "plan",
        text=plan.reasoning or "Board tasks created",
        tasks=[{"title": t["title"], "role": t["assignee_role"]} for t in board_tasks],
    )
    return {
        "plan": {
            "reasoning": plan.reasoning,
            "suggested_ui": plan.suggested_ui,
            "thinking": plan.reasoning,
            "steps": [{"title": t["title"], "detail": t["instruction"]} for t in board_tasks],
        },
        "board_tasks": board_tasks,
        "route": "board",
        "complexity": "complex" if len(board_tasks) > 1 else "simple",
        "thinking": plan.reasoning,
    }


async def coordinator_assemble(state: State) -> dict[str, Any]:
    emit_status("Coordinator assembling…")
    if state.get("waiting_approval"):
        pending = state.get("pending_approval") or {}
        msg = (
            f"Paused for approval: {pending.get('tool')} "
            f"(risk={pending.get('risk')}). Approve to continue."
        )
        return {
            "final_text": msg,
            "final_data": {"pending_approval": pending},
            "answer_streamed": False,
        }

    if state.get("needs_clarification"):
        clarification = dict(state.get("clarification") or {})
        msg = format_clarification_message(clarification)
        run_id = _run_id(state)
        if not state.get("answer_streamed"):
            reveal_text(msg, event="answer")
            emit("answer_done", text=msg)
        if run_id:
            RunStore().append_step(
                run_id,
                kind="assemble",
                text=msg[:500],
                data={"needs_clarification": True, "clarification": clarification},
            )
        return {
            "final_text": msg,
            "final_data": {"needs_clarification": True, "clarification": clarification},
            "answer_streamed": True,
        }

    run_id = _run_id(state)
    results: list[dict[str, Any]] = list(state.get("subtask_results") or [])
    if run_id:
        board = BoardStore()
        board.init_db()
        for task in board.list_for_run(run_id):
            if task.status.value in {"done", "failed"}:
                results.append(
                    {
                        "subtask_id": task.id,
                        "text": task.result_text,
                        "data": task.result_json,
                        "assignee": task.assignee_role,
                        "status": task.status.value,
                    }
                )

    # Dedupe by subtask_id
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in results:
        sid = str(row.get("subtask_id") or "")
        if sid and sid in seen:
            continue
        if sid:
            seen.add(sid)
        unique.append(row)

    parts = [str(r.get("text") or "").strip() for r in unique if r.get("text")]
    joined = "\n\n".join(parts) if parts else "No specialist results."
    merged: dict[str, Any] = {}
    for r in unique:
        for k, v in (r.get("data") or {}).items():
            if k not in merged or merged[k] in (None, "", [], {}):
                merged[k] = v
            elif isinstance(merged[k], list) and isinstance(v, list):
                merged[k] = merged[k] + v

    final_text = joined
    if parts:
        try:
            pack = coordinator()
            assemble_rules = (pack.prompts.get("assemble") or pack.instructions or "").strip()
            query = last_user_text(state.get("messages") or [])
            result_blocks: list[str] = []
            for r in unique:
                text = str(r.get("text") or "").strip()
                if not text:
                    continue
                block = f"[{r.get('assignee') or 'specialist'}]\n{text}"
                data = r.get("data") or {}
                if data:
                    try:
                        block += f"\n(data: {json.dumps(data, default=str)[:1500]})"
                    except Exception:
                        pass
                result_blocks.append(block)
            prompt = (
                f"{assemble_rules}\n\n"
                f"User request:\n{query}\n\n"
                f"Specialist results:\n" + "\n\n".join(result_blocks)
            )
            response = await get_llm(temperature=0.2).ainvoke(
                [{"role": "user", "content": prompt}]
            )
            content = response.content
            synthesized = content if isinstance(content, str) else str(content)
            if synthesized.strip():
                final_text = synthesized.strip()
        except Exception as exc:
            emit("assemble", text=f"Assemble LLM fallback: {exc}")
            final_text = joined

    if not state.get("answer_streamed"):
        reveal_text(final_text, event="answer")
        emit("answer_done", text=final_text)

    if run_id:
        RunStore().append_step(
            run_id,
            kind="assemble",
            text=final_text[:500],
            data={"result_count": len(unique)},
        )

    return {
        "final_text": final_text,
        "final_data": merged,
        "subtask_results": unique,
        "answer_streamed": True,
    }
