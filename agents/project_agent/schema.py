from __future__ import annotations

from pydantic import BaseModel, Field


class OverdueTask(BaseModel):
    id: str = ""
    title: str = ""
    project_id: str = ""
    deadline: str = ""
    status: str = ""


class Result(BaseModel):
    summary: str = ""
    overdue: list[OverdueTask] = Field(default_factory=list)
