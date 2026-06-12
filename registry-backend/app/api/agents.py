from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from prisma import Prisma

from app.auth import AuthContext, get_auth_context, get_optional_auth_context
from app.database import get_db
from app.schemas import AgentResponse, DiscoverResponse, RegisterAgentRequest, StatusResponse
from app.services import agents as agent_service
from app.services.api_keys import ensure_api_key

router = APIRouter(prefix="/v1/agents", tags=["agents"])


async def _owner_id(db: Prisma, auth: AuthContext, raw_key: str | None = None) -> uuid.UUID:
    if auth.api_key_id is not None:
        return auth.api_key_id
    if auth.is_bootstrap and raw_key:
        return await ensure_api_key(db, raw_key=raw_key, name="bootstrap")
    raise HTTPException(status_code=401, detail="Invalid API key context")


@router.post("", response_model=AgentResponse)
async def register_agent(
    body: RegisterAgentRequest,
    request: Request,
    db: Prisma = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AgentResponse:
    raw_key = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    owner_id = await _owner_id(db, auth, raw_key or None)
    return await agent_service.register_agent(db, owner_id=owner_id, body=body)


@router.post("/{agent_id}/heartbeat", response_model=StatusResponse)
async def heartbeat(
    agent_id: str,
    request: Request,
    db: Prisma = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> StatusResponse:
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc

    raw_key = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    owner_id = await _owner_id(db, auth, raw_key or None)
    try:
        await agent_service.heartbeat(db, agent_id=agent_uuid, owner_id=owner_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
    return StatusResponse()


@router.get("/discover", response_model=DiscoverResponse)
async def discover(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    exclude: str | None = Query(default=None),
    db: Prisma = Depends(get_db),
    _auth: AuthContext = Depends(get_optional_auth_context),
) -> DiscoverResponse:
    skills = request.query_params.getlist("skills")
    tags = request.query_params.getlist("tags")
    agents = await agent_service.discover_agents(
        db, skills=skills or None, tags=tags or None, limit=limit, exclude_id=exclude
    )
    return DiscoverResponse(agents=agents)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: Prisma = Depends(get_db),
    _auth: AuthContext = Depends(get_optional_auth_context),
) -> AgentResponse:
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
    try:
        return await agent_service.get_agent(db, agent_id=agent_uuid)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
