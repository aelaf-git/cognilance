"""Organization alert inbox for the caller's active organization."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from api import deps
from core.context.orgs.store import OrganizationAlert

router = APIRouter()


def _organization_id(request: Request) -> str:
    account_id = deps.user_from(request)
    organization_id = deps.active_organization_id(account_id)
    if not organization_id:
        raise HTTPException(status_code=404, detail="Not found")
    deps.require_membership(account_id, organization_id, "member")
    return organization_id


def _require_alert(alert_id: str, organization_id: str) -> OrganizationAlert:
    alert = deps.org_store.get_alert(alert_id)
    if alert is None or alert.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Not found")
    return alert


def _alert_payload(alert: OrganizationAlert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "organization_id": alert.organization_id,
        "kind": alert.kind,
        "summary": alert.summary,
        "severity": alert.severity,
        "priority": alert.priority or "normal",
        "assignee_account_id": alert.assignee_account_id,
        "read": alert.acknowledged_at is not None,
        "suggested_next_step": alert.suggested_next_step,
        "link": alert.link or {},
        "created_at": alert.created_at.isoformat(),
    }


@router.get("/alerts")
async def list_alerts(request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    rows = deps.org_store.list_open_alerts(organization_id)
    return JSONResponse({"alerts": [_alert_payload(item) for item in rows]})


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    _require_alert(alert_id, organization_id)
    deps.org_store.acknowledge_alert(alert_id)
    saved = deps.org_store.get_alert(alert_id)
    assert saved is not None
    return JSONResponse(_alert_payload(saved))


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str, request: Request) -> JSONResponse:
    organization_id = _organization_id(request)
    _require_alert(alert_id, organization_id)
    deps.org_store.dismiss_alert(alert_id)
    saved = deps.org_store.get_alert(alert_id)
    assert saved is not None
    return JSONResponse(_alert_payload(saved))
