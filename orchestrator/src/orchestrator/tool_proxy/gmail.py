"""Gmail tool proxy — hired agents call back with scoped tokens."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from orchestrator.integrations.client import IntegrationClient
from orchestrator.tool_proxy.grants import validate_callback

router = APIRouter(prefix="/tools/gmail", tags=["tool-proxy"])

_SCOPE_ACTIONS: dict[str, tuple[str, str]] = {
    "send": ("gmail:send", "send_email"),
    "list": ("gmail:read", "list_emails"),
    "read": ("gmail:read", "read_email"),
    "search": ("gmail:search", "search_emails"),
}


class GmailProxyRequest(BaseModel):
    task_id: str
    params: dict[str, Any] = Field(default_factory=dict)


def _auth_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer callback token")
    return authorization.split(" ", 1)[1].strip()


async def _execute(
    *,
    authorization: str | None,
    body: GmailProxyRequest,
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
    if not client.is_connected(user_id, "gmail"):
        raise HTTPException(status_code=400, detail="Gmail is not connected for this user")

    try:
        return await client.run(user_id, "gmail", integration_action, body.params)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/send")
async def gmail_send(
    body: GmailProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="send")


@router.post("/list")
async def gmail_list(
    body: GmailProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="list")


@router.post("/read")
async def gmail_read(
    body: GmailProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="read")


@router.post("/search")
async def gmail_search(
    body: GmailProxyRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _execute(authorization=authorization, body=body, action_key="search")
