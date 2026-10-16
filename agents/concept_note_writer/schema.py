from __future__ import annotations

from pydantic import BaseModel, Field


class Result(BaseModel):
    title: str = ""
    problem: str = ""
    objectives: list[str] = Field(default_factory=list)
    approach: str = ""
    outcomes: list[str] = Field(default_factory=list)
    timeline: str = ""
    budget_outline: str = ""
    risks: list[str] = Field(default_factory=list)
    document_id: str | None = None
    document_url: str | None = None
