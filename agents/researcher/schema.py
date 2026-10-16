from __future__ import annotations

from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str = ""
    url: str
    snippet: str = ""
    verdict: str | None = None  # ok | warning | broken


class Result(BaseModel):
    answer: str = ""
    sources: list[Source] = Field(default_factory=list)
