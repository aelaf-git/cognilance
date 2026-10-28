"""Specialist nodes: claim board tasks and execute via role tools."""

from __future__ import annotations

from typing import Any

from core.runtime.board.store import BoardStore
from core.context.request import current_mission_id
from core.runtime.runs.models import RunStatus
from core.runtime.runs.store import RunStore
from agents.loader import SPECIALISTS, get_role
from pipelines.shared.state import State, SubtaskResult
from pipelines.shared.streaming import emit, emit_status
from tools.registry import ApprovalRequired, run_role_tool


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
        # Pure reasoning / arithmetic: don't force a web call
        if any(
            w in text
            for w in ("what is", "calculate", "compute", "how many", "brief answer")
        ) and not any(w in text for w in ("research", "search", "web", "http", "news")):
            return "thinking"
        return first("web.search")
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

        tool = _pick_tool(pack.id, instruction, pack.tools)
        try:
            out = await run_role_tool(pack, tool, instruction=instruction)
            text = str(out.get("text") or "")
            data = dict(out.get("data") or {})
            if run_id:
                board.complete_task(task_id, result_text=text, result_json=data)
                runs.append_step(
                    run_id,
                    kind="task_done",
                    text=title,
                    data={"task_id": task_id, "tool": tool, "risk": out.get("risk")},
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
            # Skip if waiting approval
            if merged.get("waiting_approval") or state.get("waiting_approval"):
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
        if not progress or merged.get("waiting_approval"):
            break
    return merged
