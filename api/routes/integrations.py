"""OAuth integrations (plus legacy /apps aliases)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from api import deps
from core.context.orgs.store import ROLE_RANK

router = APIRouter()


class RepoSelection(BaseModel):
    repo_ids: list[str] = Field(default_factory=list)


def mark_github_manage(
    account_id: str, organization_id: str | None, items: list[dict]
) -> list[dict]:
    manage = False
    if organization_id:
        membership = deps.org_store.membership_for(account_id, organization_id)
        if membership and ROLE_RANK.get(membership.role, 0) >= ROLE_RANK["admin"]:
            manage = True
    for item in items:
        if item.get("id") == "github":
            item["manage"] = manage
    return items


def _audit_disconnect(
    account_id: str, integration_id: str, organization_id: str | None
) -> None:
    org_id = organization_id or deps.active_organization_id(account_id) or ""
    deps.org_store.record_audit(
        account_id, org_id, "integration.disconnected", integration_id
    )


def _active_org(account_id: str, organization_id: str = "") -> str:
    org_id = organization_id.strip() or deps.active_organization_id(account_id) or ""
    if not org_id:
        raise HTTPException(status_code=404, detail="Not found")
    return org_id


@router.get("/integrations/list")
async def list_integrations(request: Request) -> JSONResponse:
    account_id = deps.user_from(request)
    organization_id = deps.active_organization_id(account_id)
    items = deps.oauth_service.list_for_user(account_id, organization_id=organization_id)
    return JSONResponse(
        content={
            "integrations": mark_github_manage(account_id, organization_id, items)
        }
    )


@router.get("/apps")
async def list_apps_compat(request: Request) -> JSONResponse:
    account_id = deps.user_from(request)
    organization_id = deps.active_organization_id(account_id)
    items = deps.oauth_service.list_for_user(account_id, organization_id=organization_id)
    return JSONResponse(
        content={"apps": mark_github_manage(account_id, organization_id, items)}
    )


@router.get("/integrations/github/repos")
async def list_github_repos(
    request: Request, organization_id: str = ""
) -> JSONResponse:
    account_id = deps.user_from(request)
    org_id = _active_org(account_id, organization_id)
    deps.require_membership(account_id, org_id, "member")
    try:
        repos = await deps.oauth_service.list_github_repos(org_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:120]) from exc
    return JSONResponse(content={"repos": repos})


@router.put("/integrations/github/repos")
async def save_github_repos(
    body: RepoSelection, request: Request, organization_id: str = ""
) -> JSONResponse:
    account_id = deps.user_from(request)
    org_id = _active_org(account_id, organization_id)
    deps.require_membership(account_id, org_id, "admin")
    try:
        chosen = await deps.oauth_service.set_github_repos(org_id, body.repo_ids)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:120]) from exc
    return JSONResponse(content={"repo_ids": chosen})


@router.get("/integrations/{integration_id}/connect")
async def connect_integration(
    integration_id: str, request: Request, organization_id: str = ""
) -> RedirectResponse:
    account_id = deps.user_from(request)
    org_id = None
    if integration_id == "github":
        org_id = _active_org(account_id, organization_id)
        deps.require_membership(account_id, org_id, "admin")
    try:
        url = deps.oauth_service.start_oauth(
            account_id, integration_id, organization_id=org_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RedirectResponse(url=url, status_code=307)


@router.get("/integrations/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
) -> JSONResponse:
    if error:
        return JSONResponse(status_code=400, content={"error": error})
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state")
    try:
        user_id, integration_id, organization_id = await deps.oauth_service.handle_callback(
            code, state
        )
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "invalid_state"})
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)[:120]})
    org_id = organization_id or deps.active_organization_id(user_id) or ""
    deps.org_store.record_audit(user_id, org_id, "integration.connected", integration_id)
    return JSONResponse(content={"connected": integration_id})


@router.post("/integrations/{integration_id}/disconnect")
async def disconnect_integration(
    integration_id: str, request: Request, organization_id: str = ""
) -> JSONResponse:
    account_id = deps.user_from(request)
    org_id = None
    if integration_id == "github":
        org_id = _active_org(account_id, organization_id)
        deps.require_membership(account_id, org_id, "admin")
    deps.oauth_service.disconnect(account_id, integration_id, organization_id=org_id)
    _audit_disconnect(account_id, integration_id, org_id)
    return JSONResponse(content={"integration_id": integration_id, "connected": False})


@router.post("/apps/{app_id}/disconnect")
async def disconnect_app_compat(
    app_id: str, request: Request, organization_id: str = ""
) -> JSONResponse:
    account_id = deps.user_from(request)
    org_id = None
    if app_id == "github":
        org_id = _active_org(account_id, organization_id)
        deps.require_membership(account_id, org_id, "admin")
    deps.oauth_service.disconnect(account_id, app_id, organization_id=org_id)
    _audit_disconnect(account_id, app_id, org_id)
    return JSONResponse(content={"app_id": app_id, "connected": False})
