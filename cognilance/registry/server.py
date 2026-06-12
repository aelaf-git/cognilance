"""Local in-memory Cognilance registry for development."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from cognilance.core.models import AgentVisibility, TraceEvent
from cognilance.registry.dashboard import DASHBOARD_HTML
from cognilance.ui.dev_chat import registry_chat_html


class DevChatRequest(BaseModel):
    agent_url: str
    text: str = ""


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

    # ------------------------------------------------------------------
    # Trace collector + live dashboard
    # ------------------------------------------------------------------

    traces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    trace_order: list[str] = []  # most recent trace_ids last
    websockets: set[WebSocket] = set()

    async def _broadcast(message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            websockets.discard(ws)

    @app.post("/v1/traces/events")
    async def collect_event(event: TraceEvent) -> dict[str, str]:
        if event.trace_id not in traces:
            trace_order.append(event.trace_id)
        traces[event.trace_id].append(event.model_dump(mode="json"))
        await _broadcast({"kind": "event", "event": event.model_dump(mode="json")})
        return {"status": "ok"}

    def _trace_summary(trace_id: str) -> dict[str, Any]:
        events = traces[trace_id]
        root = next(
            (e for e in events if e["type"] in ("task_received", "hire_started")), events[0]
        )
        failed = any(e["type"] in ("task_failed", "hire_failed") for e in events)
        completed = any(
            e["type"] == "task_completed" and e["depth"] == 0 for e in events
        ) or any(e["type"] == "hire_completed" and e["depth"] == 0 for e in events)
        return {
            "trace_id": trace_id,
            "started_at": events[0]["timestamp"],
            "last_at": events[-1]["timestamp"],
            "root_text": root.get("text", ""),
            "root_agent": root.get("agent_name", ""),
            "event_count": len(events),
            "agents": sorted({e["agent_name"] for e in events if e["agent_name"]}),
            "status": "failed" if failed else ("completed" if completed else "working"),
        }

    @app.get("/v1/traces")
    async def list_traces(limit: int = Query(default=50, ge=1)) -> dict[str, Any]:
        recent = list(reversed(trace_order[-limit:]))
        return {"traces": [_trace_summary(t) for t in recent]}

    @app.get("/v1/traces/{trace_id}")
    async def get_trace(trace_id: str) -> dict[str, Any]:
        if trace_id not in traces:
            raise HTTPException(status_code=404, detail="Trace not found")
        return {"trace_id": trace_id, "events": traces[trace_id]}

    @app.websocket("/v1/traces/ws")
    async def trace_ws(ws: WebSocket) -> None:
        await ws.accept()
        websockets.add(ws)
        try:
            while True:
                # Block until the client disconnects; clients never send data.
                await ws.receive_text()
        except (WebSocketDisconnect, Exception):
            websockets.discard(ws)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/dev/chat", response_class=HTMLResponse)
    async def dev_chat() -> str:
        """Built-in browser UI to test any registered agent."""
        return registry_chat_html()

    @app.post("/v1/dev/chat")
    async def dev_chat_proxy(body: DevChatRequest) -> JSONResponse:
        """Proxy chat messages to an agent (avoids browser CORS during local dev)."""
        url = body.agent_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{url}/a2a/tasks",
                    json={"input": {"text": body.text}},
                )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Agent unreachable: {exc}") from exc

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return JSONResponse(content=response.json())

    return app
