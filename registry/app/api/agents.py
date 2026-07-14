from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from prisma import Prisma

from app.database import get_db
from app.schemas import (
    AgentResponse,
    DiscoverResponse,
    RegisterAgentRequest,
    StatusResponse,
    UpdateAgentPaymentRequest,
)
from app.services import agents as agent_service

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post("", response_model=AgentResponse)
async def register_agent(
    body: RegisterAgentRequest,
    db: Prisma = Depends(get_db),
) -> AgentResponse:
    try:
        return await agent_service.register_agent(db, body=body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{agent_id}/payment", response_model=AgentResponse)
async def update_agent_payment(
    agent_id: str,
    body: UpdateAgentPaymentRequest,
    db: Prisma = Depends(get_db),
) -> AgentResponse:
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
    try:
        return await agent_service.update_agent_payment(
            db, agent_id=agent_uuid, body=body
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{agent_id}/heartbeat", response_model=StatusResponse)
async def heartbeat(
    agent_id: str,
    db: Prisma = Depends(get_db),
) -> StatusResponse:
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc

    try:
        await agent_service.heartbeat(db, agent_id=agent_uuid)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
    return StatusResponse()


@router.get("/discover", response_model=DiscoverResponse)
async def discover(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    exclude: str | None = Query(default=None),
    db: Prisma = Depends(get_db),
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
) -> AgentResponse:
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
    try:
        return await agent_service.get_agent(db, agent_id=agent_uuid)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Agent not found") from exc
