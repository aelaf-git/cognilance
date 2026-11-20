"""Organization membership, invitations, and tenant-scoped lists."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from api import deps
from core.context.orgs.store import Invitation

router = APIRouter()


def _raise_invitation(exc: ValueError) -> None:
    message = str(exc)
    if message in {"Invitation not found", "Organization not found"}:
        raise HTTPException(status_code=404, detail="Not found") from exc
    if message == "This invitation is for a different email":
        raise HTTPException(status_code=403, detail="Forbidden") from exc
    if message == "An invitation for that email is already pending":
        raise HTTPException(status_code=409, detail=message) from exc
    raise HTTPException(status_code=400, detail=message) from exc


def _invitation_payload(invitation: Invitation) -> dict[str, Any]:
    organization = deps.org_store.get_organization(invitation.organization_id)
    return {
        "id": invitation.id,
        "organization_id": invitation.organization_id,
        "organization_name": organization.name if organization else "",
        "email": invitation.email,
        "role": invitation.role,
        "token": invitation.token,
        "created_at": invitation.created_at.isoformat(),
    }


def _signed_in_account(request: Request):
    account = deps.account_store.get_by_id(deps.user_from(request))
    if not account:
        raise HTTPException(status_code=401, detail="Authentication required")
    return account


@router.get("/organizations")
async def list_organizations(request: Request) -> JSONResponse:
    account_id = deps.user_from(request)
    organizations = []
    for membership in deps.org_store.memberships_for(account_id):
        organization = deps.org_store.get_organization(membership.organization_id)
        organizations.append(
            {
                "id": membership.organization_id,
                "name": organization.name if organization else "",
                "role": membership.role,
            }
        )
    return JSONResponse({"organizations": organizations})


@router.post("/organizations/{organization_id}/invitations")
async def create_invitation(organization_id: str, request: Request) -> JSONResponse:
    account_id = deps.user_from(request)
    deps.require_membership(account_id, organization_id, "admin")
    payload: dict[str, Any] = await request.json()
    role = payload.get("role")
    try:
        invitation = deps.org_store.create_invitation(
            organization_id,
            str(payload.get("email") or ""),
            created_by=account_id,
            role=str(role) if role else "member",
        )
    except ValueError as exc:
        _raise_invitation(exc)
    return JSONResponse(_invitation_payload(invitation))


@router.get("/invitations")
async def list_invitations(request: Request) -> JSONResponse:
    account = _signed_in_account(request)
    pending = deps.org_store.pending_invitations_for_email(account.email)
    return JSONResponse(
        {"invitations": [_invitation_payload(item) for item in pending]}
    )


@router.post("/invitations/{token}/accept")
async def accept_invitation(token: str, request: Request) -> JSONResponse:
    account = _signed_in_account(request)
    try:
        membership = deps.org_store.accept_invitation(token, account)
    except ValueError as exc:
        _raise_invitation(exc)
    if membership is None:
        return JSONResponse({"accepted": True})
    return JSONResponse(
        {
            "organization_id": membership.organization_id,
            "account_id": membership.account_id,
            "role": membership.role,
        }
    )


@router.get("/organizations/{organization_id}/conversations")
async def list_organization_conversations(
    organization_id: str, request: Request
) -> JSONResponse:
    deps.require_membership(deps.user_from(request), organization_id, "member")
    rows = deps.conv_store.list_conversations(organization_id=organization_id)
    return JSONResponse(
        {
            "conversations": [
                {
                    "id": row.id,
                    "title": row.title,
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat(),
                    "organization_id": row.organization_id,
                }
                for row in rows
            ]
        }
    )


@router.get("/organizations/{organization_id}/runs")
async def list_organization_runs(organization_id: str, request: Request) -> JSONResponse:
    deps.require_membership(deps.user_from(request), organization_id, "member")
    runs = deps.run_store.list_for_organization(organization_id)
    return JSONResponse({"runs": [run.to_dict() for run in runs]})


@router.get("/organizations/{organization_id}/integrations")
async def list_organization_integrations(
    organization_id: str, request: Request
) -> JSONResponse:
    account_id = deps.user_from(request)
    deps.require_membership(account_id, organization_id, "member")
    from api.routes.integrations import mark_github_manage

    items = deps.oauth_service.list_for_user(account_id, organization_id=organization_id)
    return JSONResponse(
        {"integrations": mark_github_manage(account_id, organization_id, items)}
    )


@router.post("/organizations/{organization_id}/schedules")
async def create_organization_schedule(
    organization_id: str, request: Request
) -> JSONResponse:
    account_id = deps.user_from(request)
    deps.require_membership(account_id, organization_id, "admin")
    payload: dict[str, Any] = await request.json()
    from core.context.subscriptions.schedule import create_weekly_schedule

    try:
        created = create_weekly_schedule(
            organization_id=organization_id,
            user_id=account_id,
            payload=payload,
            org_store=deps.org_store,
            sub_store=deps.sub_store,
            mission_store=deps.mission_store,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(created)


@router.delete("/organizations/{organization_id}")
async def delete_organization(organization_id: str, request: Request) -> JSONResponse:
    deps.require_membership(deps.user_from(request), organization_id, "owner")
    deps.org_store.delete_organization(organization_id)
    return JSONResponse({"deleted": True})
