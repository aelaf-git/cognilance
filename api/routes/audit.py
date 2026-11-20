"""Append-only audit read for the caller's active organization."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from api import deps
from core.context.orgs.store import AuditEvent

router = APIRouter()


def _organization_id(request: Request) -> str:
    account_id = deps.user_from(request)
    organization_id = deps.active_organization_id(account_id)
    if not organization_id:
        raise HTTPException(status_code=404, detail="Not found")
    deps.require_membership(account_id, organization_id, "admin")
    return organization_id


def _event_payload(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "actor_account_id": event.actor_account_id,
        "organization_id": event.organization_id,
        "action": event.action,
        "target_id": event.target_id,
        "created_at": event.created_at.isoformat(),
    }


@router.get("/audit")
async def list_audit(request: Request, action: str = "") -> JSONResponse:
    organization_id = _organization_id(request)
    events = deps.org_store.list_audit(organization_id, action)
    return JSONResponse({"events": [_event_payload(event) for event in events]})
