from __future__ import annotations

from pydantic import BaseModel, Field


class GitHubItem(BaseModel):
    title: str = ""
    url: str = ""
    timestamp: str = ""
    kind: str = ""


class MatchedTask(BaseModel):
    id: str = ""
    title: str = ""


class Result(BaseModel):
    summary: str = ""
    items: list[GitHubItem] = Field(default_factory=list)
    matched_tasks: list[MatchedTask] = Field(default_factory=list)
