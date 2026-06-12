"""Pydantic request/response schemas (SDK-compatible)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RegisterAgentRequest(BaseModel):
    name: str
    url: str
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    visibility: str = "public"
    tags: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    id: str
    name: str
    url: str
    description: str = ""
    skills: list[dict[str, Any]]
    visibility: str
    tags: list[str] = Field(default_factory=list)
    online: bool = True
    last_heartbeat: datetime
    version: str = "0.1.0"


class DiscoverResponse(BaseModel):
    agents: list[AgentResponse]


class TraceEventIn(BaseModel):
    id: str | None = None
    trace_id: str
    task_id: str
    parent_task_id: str | None = None
    depth: int = 0
    agent_name: str = ""
    type: str
    text: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None


class TraceEventOut(TraceEventIn):
    id: str
    timestamp: datetime


class TraceSummary(BaseModel):
    trace_id: str
    started_at: datetime
    last_at: datetime
    root_text: str = ""
    root_agent: str = ""
    event_count: int
    agents: list[str]
    status: str


class TraceListResponse(BaseModel):
    traces: list[TraceSummary]


class TraceDetailResponse(BaseModel):
    trace_id: str
    events: list[dict[str, Any]]


class StatusResponse(BaseModel):
    status: str = "ok"


class CreateApiKeyRequest(BaseModel):
    name: str = "default"


class CreateApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key: str
    prefix: str
