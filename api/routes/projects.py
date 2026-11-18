"""Organization projects and work tasks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from api import deps
from core.context.projects.store import Project, WorkTask, WorkTaskActivity, WorkTaskComment

router = APIRouter()


def _organization_id(request: Request) -> str:
    account_id = deps.user_from(request)
    organization_id = deps.active_organization_id(account_id)
    if not organization_id:
        raise HTTPException(status_code=404, detail="Not found")
    deps.require_membership(account_id, organization_id, "member")
    return organization_id


def _raise_value(exc: ValueError) -> None:
    message = str(exc)
    if message in {"Project not found", "Task not found"}:
        raise HTTPException(status_code=404, detail="Not found") from exc
    raise HTTPException(status_code=400, detail=message) from exc


def _project_payload(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "organization_id": project.organization_id,
        "title": project.title,
        "created_by": project.created_by,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


def _task_payload(task: WorkTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "project_id": task.project_id,
        "organization_id": task.organization_id,
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "deadline": task.deadline,
        "assignee_account_id": task.assignee_account_id,
        "assignee_agent_id": task.assignee_agent_id,
        "created_by": task.created_by,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def _comment_payload(comment: WorkTaskComment) -> dict[str, Any]:
    return {
        "id": comment.id,
        "task_id": comment.task_id,
        "author_id": comment.author_id,
        "body": comment.body,
        "created_at": comment.created_at.isoformat(),
    }


def _activity_payload(row: WorkTaskActivity) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "actor_id": row.actor_id,
        "action": row.action,
        "payload": row.payload,
        "created_at": row.created_at.isoformat(),
    }


def _check_account_assignee(organization_id: str, account_id: str | None) -> None:
    if not account_id:
        return
    if deps.org_store.membership_for(account_id, organization_id) is None:
        raise HTTPException(status_code=400, detail="Assignee is not a member")


@router.get("/projects")
async def list_projects(request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    projects = deps.project_store.list_projects(organization_id)
    return JSONResponse({"projects": [_project_payload(item) for item in projects]})


@router.post("/projects")
async def create_project(request: Request) -> JSONResponse:
    account_id = deps.user_from(request)
    organization_id = _organization_id(request)
    payload: dict[str, Any] = await request.json()
    try:
        project = deps.project_store.create_project(
            organization_id,
            str(payload.get("title") or ""),
            created_by=account_id,
        )
    except ValueError as exc:
        _raise_value(exc)
    return JSONResponse(_project_payload(project))


@router.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    project = deps.project_store.get_project(project_id, organization_id=organization_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse(_project_payload(project))


@router.patch("/projects/{project_id}")
async def update_project(project_id: str, request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    payload: dict[str, Any] = await request.json()
    try:
        project = deps.project_store.update_project(
            project_id,
            organization_id=organization_id,
            title=str(payload.get("title") or ""),
        )
    except ValueError as exc:
        _raise_value(exc)
    if project is None:
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse(_project_payload(project))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    if not deps.project_store.delete_project(project_id, organization_id=organization_id):
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse({"deleted": True})


@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str, request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    try:
        tasks = deps.project_store.list_tasks(project_id, organization_id=organization_id)
    except ValueError as exc:
        _raise_value(exc)
    return JSONResponse({"tasks": [_task_payload(item) for item in tasks]})


@router.post("/projects/{project_id}/tasks")
async def create_task(project_id: str, request: Request) -> JSONResponse:
    account_id = deps.user_from(request)
    organization_id = _organization_id(request)
    payload: dict[str, Any] = await request.json()
    assignee_account = payload.get("assignee_account_id")
    _check_account_assignee(
        organization_id, str(assignee_account) if assignee_account else None
    )
    try:
        task = deps.project_store.create_task(
            project_id,
            organization_id=organization_id,
            title=str(payload.get("title") or ""),
            created_by=account_id,
            status=str(payload.get("status") or "open"),
            priority=str(payload.get("priority") or "normal"),
            deadline=payload.get("deadline"),
            assignee_account_id=str(assignee_account) if assignee_account else None,
            assignee_agent_id=(
                str(payload.get("assignee_agent_id"))
                if payload.get("assignee_agent_id")
                else None
            ),
        )
    except ValueError as exc:
        _raise_value(exc)
    return JSONResponse(_task_payload(task))


@router.get("/projects/{project_id}/tasks/{task_id}")
async def get_task(project_id: str, task_id: str, request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    task = deps.project_store.get_task(task_id, organization_id=organization_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse(_task_payload(task))


@router.patch("/projects/{project_id}/tasks/{task_id}")
async def update_task(project_id: str, task_id: str, request: Request) -> JSONResponse:
    account_id = deps.user_from(request)
    organization_id = _organization_id(request)
    current = deps.project_store.get_task(task_id, organization_id=organization_id)
    if current is None or current.project_id != project_id:
        raise HTTPException(status_code=404, detail="Not found")
    payload: dict[str, Any] = await request.json()
    kwargs: dict[str, Any] = {}
    if "title" in payload:
        kwargs["title"] = payload.get("title")
    if "status" in payload:
        kwargs["status"] = payload.get("status")
    if "priority" in payload:
        kwargs["priority"] = payload.get("priority")
    if "deadline" in payload:
        kwargs["deadline"] = payload.get("deadline")
    if "assignee_account_id" in payload:
        assignee_account = payload.get("assignee_account_id")
        _check_account_assignee(
            organization_id, str(assignee_account) if assignee_account else None
        )
        kwargs["assignee_account_id"] = assignee_account
    if "assignee_agent_id" in payload:
        kwargs["assignee_agent_id"] = payload.get("assignee_agent_id")
    try:
        task = deps.project_store.update_task(
            task_id,
            organization_id=organization_id,
            actor_id=account_id,
            **kwargs,
        )
    except ValueError as exc:
        _raise_value(exc)
    if task is None:
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse(_task_payload(task))


@router.delete("/projects/{project_id}/tasks/{task_id}")
async def delete_task(project_id: str, task_id: str, request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    current = deps.project_store.get_task(task_id, organization_id=organization_id)
    if current is None or current.project_id != project_id:
        raise HTTPException(status_code=404, detail="Not found")
    deps.project_store.delete_task(task_id, organization_id=organization_id)
    return JSONResponse({"deleted": True})


@router.post("/projects/{project_id}/tasks/{task_id}/comments")
async def add_comment(project_id: str, task_id: str, request: Request) -> JSONResponse:
    account_id = deps.user_from(request)
    organization_id = _organization_id(request)
    current = deps.project_store.get_task(task_id, organization_id=organization_id)
    if current is None or current.project_id != project_id:
        raise HTTPException(status_code=404, detail="Not found")
    payload: dict[str, Any] = await request.json()
    try:
        comment = deps.project_store.add_comment(
            task_id,
            organization_id=organization_id,
            author_id=account_id,
            body=str(payload.get("body") or ""),
        )
    except ValueError as exc:
        _raise_value(exc)
    return JSONResponse(_comment_payload(comment))


@router.get("/projects/{project_id}/tasks/{task_id}/activity")
async def list_activity(project_id: str, task_id: str, request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    current = deps.project_store.get_task(task_id, organization_id=organization_id)
    if current is None or current.project_id != project_id:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        rows = deps.project_store.list_activity(task_id, organization_id=organization_id)
    except ValueError as exc:
        _raise_value(exc)
    return JSONResponse({"activity": [_activity_payload(item) for item in rows]})
