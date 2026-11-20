"""Work-task tool. Every read and write stays in the run's organization."""

from __future__ import annotations

import json
from typing import Any

from core.context.projects.store import STATUSES, ProjectStore, WorkTask
from core.context.request import current_mission_id
from core.runtime.runs.store import RunStore
from tools.registry import ToolContext, ToolOutput


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


def _invalid(fields: list[str]) -> ToolOutput:
    names = ", ".join(fields)
    return ToolOutput(
        text=f"Invalid parameters: {names}",
        data={"error": "invalid_params", "fields": fields},
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


def _bad_status(body: dict[str, Any]) -> bool:
    if "status" not in body:
        return False
    status = str(body.get("status") or "").strip().lower()
    return not status or status not in STATUSES


async def run(
    action: str,
    *,
    instruction: str,
    params: dict[str, Any],
    ctx: ToolContext,
) -> ToolOutput:
    if action not in {"search", "create", "update"}:
        raise RuntimeError(f"Unknown tasks action: {action}")
    organization_id = _organization_id()
    if not organization_id:
        return _missing_org()
    body = _instruction_params(instruction, params)
    if _bad_status(body):
        return _invalid(["status"])
    store = ProjectStore()
    store.init_db()
    actor = str(ctx.role_id or "").strip() or "tasks"
    try:
        if action == "search":
            status = str(body.get("status") or "").strip().lower() or None
            tasks = store.search_tasks(
                organization_id,
                query=str(body.get("query") or ""),
                status=status,
            )
            lines = [f"- {task.title} ({task.id}, {task.status})" for task in tasks]
            text = "\n".join(lines) if lines else "No tasks."
            return ToolOutput(text=text, data={"tasks": [_task_row(task) for task in tasks]})
        if action == "create":
            project_id = str(body.get("project_id") or "").strip()
            title = str(body.get("title") or "").strip()
            missing = [name for name, value in (("project_id", project_id), ("title", title)) if not value]
            if missing:
                return _invalid(missing)
            task = store.create_task(
                project_id,
                organization_id=organization_id,
                title=title,
                created_by=actor,
                status=str(body.get("status") or "open"),
                priority=str(body.get("priority") or "normal"),
                deadline=body.get("deadline"),
                assignee_account_id=body.get("assignee_account_id"),
                assignee_agent_id=body.get("assignee_agent_id"),
            )
            return ToolOutput(text=f"Created {task.title}", data={"task": _task_row(task)})
        task_id = str(body.get("task_id") or "").strip()
        if not task_id:
            return _invalid(["task_id"])
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
