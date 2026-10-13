"""Google Docs tool proxy — hired agents call back with scoped tokens."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from orchestrator.integrations.client import IntegrationClient
from orchestrator.tool_proxy.grants import validate_callback

router = APIRouter(prefix="/tools/docs", tags=["tool-proxy"])

_SCOPE_ACTIONS: dict[str, tuple[str, str]] = {
    "create": ("docs:write", "create_document"),
    "read": ("docs:read", "read_document"),
    "write": ("docs:write", "write_document"),
    "batch_update": ("docs:write", "batch_update_document"),
    "export": ("docs:read", "export_document"),
    "insert_table": ("docs:write", "insert_table"),
    "insert_image": ("docs:write", "insert_image"),
}


class DocsProxyRequest(BaseModel):
    task_id: str
    params: dict[str, Any] = Field(default_factory=dict)


def _auth_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer callback token")
    return authorization.split(" ", 1)[1].strip()


async def _execute(
    *,
    authorization: str | None,
    body: DocsProxyRequest,
    action_key: str,
) -> dict[str, Any]:
    required_scope, integration_action = _SCOPE_ACTIONS[action_key]
    token = _auth_token(authorization)
    try:
        grant = validate_callback(token, task_id=body.task_id, required_scope=required_scope)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    user_id = str(grant["user_id"])
    client = IntegrationClient()
    if not client.is_connected(user_id, "google-drive"):
        raise HTTPException(
            status_code=400,
            detail="Google Drive is not connected for this user",
        )

    try:
        return await client.run(user_id, "google-drive", integration_action, body.params)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/create")
async def docs_create(
    body: DocsProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="create")


@router.post("/read")
async def docs_read(
    body: DocsProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="read")


@router.post("/write")
async def docs_write(
    body: DocsProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="write")


@router.post("/batch_update")
async def docs_batch_update(
    body: DocsProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="batch_update")


@router.post("/export")
async def docs_export(
    body: DocsProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="export")


@router.post("/insert_table")
async def docs_insert_table(
    body: DocsProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="insert_table")


@router.post("/insert_image")
async def docs_insert_image(
    body: DocsProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="insert_image")
