"""A2A-compatible data models for Cognilance agents."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"


class Skill(BaseModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def from_name(cls, name: str, *, tags: list[str] | None = None) -> Skill:
        slug = name.lower().replace(" ", "-")
        return cls(id=slug, name=name, tags=tags or [])


class AgentCapabilities(BaseModel):
    streaming: bool = False
    push_notifications: bool = False


class AgentCard(BaseModel):
    """A2A Agent Card exposed at GET /a2a."""

    id: str | None = None
    name: str
    description: str = ""
    url: str
    version: str = "0.1.0"
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    default_input_modes: list[str] = Field(default_factory=lambda: ["text/plain"])
    default_output_modes: list[str] = Field(default_factory=lambda: ["text/plain"])
    skills: list[Skill] = Field(default_factory=list)
    visibility: AgentVisibility = AgentVisibility.PUBLIC
    tags: list[str] = Field(default_factory=list)
    online: bool = True

    def to_a2a_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities.model_dump(),
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
            "skills": [s.model_dump() for s in self.skills],
        }


class TaskInput(BaseModel):
    text: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class TaskOutput(BaseModel):
    text: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class TaskStatus(BaseModel):
    state: TaskState
    message: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Task(BaseModel):
    """Incoming A2A task received by an agent handler."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = Field(
        default_factory=lambda: TaskStatus(state=TaskState.SUBMITTED)
    )
    input: TaskInput = Field(default_factory=TaskInput)
    output: TaskOutput | None = None

    @classmethod
    def from_a2a_payload(cls, payload: dict[str, Any]) -> Task:
        task_id = payload.get("id", str(uuid.uuid4()))
        status_data = payload.get("status", {})
        state = TaskState(status_data.get("state", TaskState.SUBMITTED))

        raw_input = payload.get("input", {})
        if "message" in raw_input:
            parts = raw_input["message"].get("parts", [])
            text_parts = [p.get("text", "") for p in parts if p.get("type") == "text"]
            text = "\n".join(text_parts)
            data = {
                p.get("data", {})
                for p in parts
                if p.get("type") == "data" and p.get("data")
            }
            merged_data: dict[str, Any] = {}
            for d in data:
                if isinstance(d, dict):
                    merged_data.update(d)
            task_input = TaskInput(text=text, data=merged_data)
        else:
            task_input = TaskInput(
                text=raw_input.get("text", ""),
                data=raw_input.get("data", {}),
            )

        return cls(
            id=task_id,
            status=TaskStatus(state=state),
            input=task_input,
        )

    def complete(self, *, text: str = "", data: dict[str, Any] | None = None) -> Task:
        self.output = TaskOutput(text=text, data=data or {})
        self.status = TaskStatus(state=TaskState.COMPLETED)
        return self

    def fail(self, *, message: str = "Task failed") -> Task:
        self.status = TaskStatus(state=TaskState.FAILED, message=message)
        return self

    def to_a2a_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "status": {
                "state": self.status.state.value,
                "timestamp": self.status.timestamp.isoformat(),
            },
        }
        if self.status.message:
            result["status"]["message"] = self.status.message
        if self.output:
            result["output"] = {
                "text": self.output.text,
                "data": self.output.data,
            }
        return result


class TaskResult(BaseModel):
    """Result returned from hiring another agent."""

    id: str
    status: TaskStatus
    output: TaskOutput = Field(default_factory=TaskOutput)

    @classmethod
    def from_a2a_payload(cls, payload: dict[str, Any]) -> TaskResult:
        status_data = payload.get("status", {})
        state = TaskState(status_data.get("state", TaskState.COMPLETED))
        status = TaskStatus(
            state=state,
            message=status_data.get("message"),
        )

        raw_output = payload.get("output", {})
        output = TaskOutput(
            text=raw_output.get("text", ""),
            data=raw_output.get("data", {}),
        )

        return cls(id=payload.get("id", ""), status=status, output=output)
