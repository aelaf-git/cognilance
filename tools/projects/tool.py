"""Project and work-task tool. Every read and write stays in the run's organization."""

from __future__ import annotations

import json
from typing import Any

from core.context.projects.store import ProjectStore, WorkTask, is_overdue
from core.context.request import current_mission_id
from core.runtime.runs.store import RunStore
from tools.registry import ToolContext, ToolOutput


def _flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


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
    elif text and "query" not in body:
        body["query"] = text
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


def _missing_org() -> ToolOutput:
    return ToolOutput(
        text="No organization is set for this run.",
        data={"error": "no organization"},
        status="error",
    )


def _task_row(task: WorkTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "project_id": task.project_id,
        "deadline": task.deadline or "",
        "status": task.status,
        "priority": task.priority,
        "organization_id": task.organization_id,
    }


def _overdue_row(task: WorkTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "project_id": task.project_id,
        "deadline": task.deadline or "",
        "status": task.status,
    }


def _result(tasks: list[WorkTask]) -> dict[str, Any]:
    overdue = [task for task in tasks if is_overdue(task)]
    if overdue:
        summary = "Overdue: " + "; ".join(task.title for task in overdue)
    else:
        summary = "Overdue: 0"
    return {"summary": summary, "overdue": [_overdue_row(task) for task in overdue]}


def _overdue_text(tasks: list[WorkTask]) -> str:
    overdue = [task for task in tasks if is_overdue(task)]
    lines = [f"Overdue: {len(overdue)}"]
    for task in overdue:
        lines.append(f"- {task.title} ({task.status}, due {task.deadline})")
    return "\n".join(lines)


def _task_list_text(tasks: list[WorkTask]) -> str:
    lines = [f"- {task.title} ({task.id}, {task.status})" for task in tasks]
    summary = _overdue_text(tasks)
    if not lines:
        return summary
    return "\n".join(lines) + "\n" + summary


async def run(
    action: str,
    *,
    instruction: str,
    params: dict[str, Any],
    ctx: ToolContext,
) -> ToolOutput:
    body = _instruction_params(instruction, params)
    organization_id = _organization_id()
    if not organization_id:
        return _missing_org()
    store = ProjectStore()
    store.init_db()
    actor = str(ctx.role_id or "").strip() or "project_agent"
    try:
        if action == "search":
            projects = store.search_projects(organization_id, query=str(body.get("query") or ""))
            rows = [
                {"id": item.id, "title": item.title, "organization_id": item.organization_id}
                for item in projects
            ]
            text = "\n".join(f"- {item.title}" for item in projects) or "No projects."
            return ToolOutput(text=text, data={"projects": rows})
        if action == "search_tasks":
            status = str(body.get("status") or "").strip() or None
            overdue_only = _flag(body.get("overdue"))
            tasks = store.search_tasks(
                organization_id,
                query=str(body.get("query") or ""),
                status=status,
                overdue=overdue_only,
            )
            return ToolOutput(
                text=_overdue_text(tasks) if overdue_only else _task_list_text(tasks),
                data={"tasks": [_task_row(task) for task in tasks], "result": _result(tasks)},
            )
        if action == "create_task":
            task = store.create_task(
                str(body.get("project_id") or ""),
                organization_id=organization_id,
                title=str(body.get("title") or ""),
                created_by=actor,
                status=str(body.get("status") or "open"),
                priority=str(body.get("priority") or "normal"),
                deadline=body.get("deadline"),
                assignee_account_id=body.get("assignee_account_id"),
                assignee_agent_id=body.get("assignee_agent_id"),
            )
            return ToolOutput(text=f"Created {task.title}", data={"task": _task_row(task)})
        if action == "update_task":
            task_id = str(body.get("task_id") or "").strip()
            if not task_id:
                return ToolOutput(text="Task not found", data={"error": "not found"}, status="error")
            fields: dict[str, Any] = {}
            for key in ("title", "status", "priority", "deadline", "assignee_account_id", "assignee_agent_id"):
                if key in body:
                    fields[key] = body.get(key)
            task = store.update_task(
                task_id,
                organization_id=organization_id,
                actor_id=actor,
                **fields,
            )
            if task is None:
                return ToolOutput(text="Task not found", data={"error": "not found"}, status="error")
            return ToolOutput(text=f"Updated {task.title}", data={"task": _task_row(task)})
    except ValueError as exc:
        return ToolOutput(text=str(exc), data={"error": str(exc)}, status="error")
    raise RuntimeError(f"Unknown projects action: {action}")
