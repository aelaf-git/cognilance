"""Account registration, login, and profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from api.auth.session import clear_user_cookie, set_user_cookie
from api.deps import account_store, user_from
from core.context.users.timezone import (
    get_stored_user_timezone,
    persist_user_timezone,
)

router = APIRouter(prefix="/auth")


def _profile(account_id: str) -> dict[str, Any]:
    account = account_store.get_by_id(account_id)
    if not account:
        raise HTTPException(status_code=401, detail="Authentication required")
    return account_store.to_dict(
        account,
        timezone_name=get_stored_user_timezone(account.id),
    )


@router.post("/register")
async def register(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    email = str(payload.get("email") or "")
    password = str(payload.get("password") or "")
    display_name = payload.get("display_name")
    try:
        account = account_store.create(
            email=email,
            password=password,
            display_name=str(display_name) if display_name is not None else None,
        )
    except ValueError as exc:
        message = str(exc)
        status = 409 if "already exists" in message.lower() else 400
        raise HTTPException(status_code=status, detail=message) from exc
    out = JSONResponse(content=_profile(account.id))
    set_user_cookie(out, account.id)
    return out


@router.post("/login")
async def login(request: Request) -> JSONResponse:
    payload: dict[str, Any] = await request.json()
    email = str(payload.get("email") or "")
    password = str(payload.get("password") or "")
    account = account_store.authenticate(email, password)
    if not account:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    out = JSONResponse(content=_profile(account.id))
    set_user_cookie(out, account.id)
    return out


@router.post("/logout")
async def logout() -> JSONResponse:
    out = JSONResponse(content={"logged_out": True})
    clear_user_cookie(out)
    return out


@router.get("/me")
async def me(request: Request) -> JSONResponse:
    return JSONResponse(content=_profile(user_from(request)))


@router.patch("/me")
async def patch_me(request: Request) -> JSONResponse:
    account_id = user_from(request)
    payload: dict[str, Any] = await request.json()
    display_name = payload.get("display_name")
    if display_name is not None:
        updated = account_store.update_profile(
            account_id, display_name=str(display_name)
        )
        if not updated:
            raise HTTPException(status_code=401, detail="Authentication required")
    if "timezone" in payload:
        persist_user_timezone(account_id, str(payload.get("timezone") or ""))
    return JSONResponse(content=_profile(account_id))


@router.post("/password")
async def change_password(request: Request) -> JSONResponse:
    account_id = user_from(request)
    payload: dict[str, Any] = await request.json()
    try:
        account_store.change_password(
            account_id,
            current_password=str(payload.get("current_password") or ""),
            new_password=str(payload.get("new_password") or ""),
        )
    except ValueError as exc:
        message = str(exc)
        status = 401 if message == "Authentication required" else 400
        raise HTTPException(status_code=status, detail=message) from exc
    return JSONResponse(content={"updated": True})
