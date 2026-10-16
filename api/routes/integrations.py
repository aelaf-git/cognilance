"""OAuth integrations (plus legacy /apps aliases)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from api.deps import oauth_service, user_from

router = APIRouter()


@router.get("/integrations/list")
async def list_integrations(request: Request) -> JSONResponse:
    return JSONResponse(content={"integrations": oauth_service.list_for_user(user_from(request))})


@router.get("/apps")
async def list_apps_compat(request: Request) -> JSONResponse:
    return JSONResponse(content={"apps": oauth_service.list_for_user(user_from(request))})


@router.get("/integrations/{integration_id}/connect")
async def connect_integration(integration_id: str, request: Request) -> RedirectResponse:
    try:
        url = oauth_service.start_oauth(user_from(request), integration_id)
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
        _user_id, integration_id = await oauth_service.handle_callback(code, state)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "invalid_state"})
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)[:120]})
    return JSONResponse(content={"connected": integration_id})


@router.post("/integrations/{integration_id}/disconnect")
async def disconnect_integration(integration_id: str, request: Request) -> JSONResponse:
    oauth_service.disconnect(user_from(request), integration_id)
    return JSONResponse(content={"integration_id": integration_id, "connected": False})


@router.post("/apps/{app_id}/disconnect")
async def disconnect_app_compat(app_id: str, request: Request) -> JSONResponse:
    oauth_service.disconnect(user_from(request), app_id)
    return JSONResponse(content={"app_id": app_id, "connected": False})
