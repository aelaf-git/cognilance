"""Local in-memory Cognilance registry for development."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from cognilance.core.models import AgentVisibility


class RegisterAgentRequest(BaseModel):
    name: str
    url: str
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    visibility: str = AgentVisibility.PUBLIC.value
    tags: list[str] = Field(default_factory=list)


class AgentRecord(BaseModel):
    id: str
    name: str
    url: str
    description: str = ""
    skills: list[dict[str, Any]]
    visibility: str
    tags: list[str] = Field(default_factory=list)
    online: bool = True
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "0.1.0"


def create_registry_app() -> FastAPI:
    app = FastAPI(title="Cognilance Registry")
    agents: dict[str, AgentRecord] = {}

    def _to_response(record: AgentRecord) -> dict[str, Any]:
        return record.model_dump(mode="json")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/agents")
    async def register_agent(body: RegisterAgentRequest) -> dict[str, Any]:
        agent_id = str(uuid.uuid4())
        skills = [
            {"id": s.lower().replace(" ", "-"), "name": s, "description": "", "tags": []}
            for s in body.skills
        ]
        record = AgentRecord(
            id=agent_id,
            name=body.name,
            url=body.url,
            description=body.description,
            skills=skills,
            visibility=body.visibility,
            tags=body.tags,
        )
        agents[agent_id] = record
        return _to_response(record)

    @app.post("/v1/agents/{agent_id}/heartbeat")
    async def heartbeat(agent_id: str) -> dict[str, str]:
        record = agents.get(agent_id)
        if not record:
            raise HTTPException(status_code=404, detail="Agent not found")
        record.online = True
        record.last_heartbeat = datetime.now(timezone.utc)
        return {"status": "ok"}

    @app.get("/v1/agents/discover")
    async def discover(
        request: Request,
        limit: int = Query(default=10, ge=1),
        exclude: str | None = Query(default=None),
    ) -> dict[str, Any]:
        skills = request.query_params.getlist("skills")
        tags = request.query_params.getlist("tags")

        results: list[AgentRecord] = []
        for record in agents.values():
            if exclude and record.id == exclude:
                continue
            if record.visibility == AgentVisibility.PRIVATE.value:
                continue
            if skills:
                agent_skills = {s["id"] for s in record.skills} | {s["name"] for s in record.skills}
                if not all(s in agent_skills for s in skills):
                    continue
            if tags and not all(t in record.tags for t in tags):
                continue
            results.append(record)

        results.sort(key=lambda r: r.last_heartbeat, reverse=True)
        return {"agents": [_to_response(r) for r in results[:limit]]}

    @app.get("/v1/agents/{agent_id}")
    async def get_agent(agent_id: str) -> dict[str, Any]:
        record = agents.get(agent_id)
        if not record:
            raise HTTPException(status_code=404, detail="Agent not found")
        return _to_response(record)

    return app
