from __future__ import annotations

from pydantic import BaseModel, Field


class Section(BaseModel):
    heading: str
    body: str


class Result(BaseModel):
    title: str = ""
    sections: list[Section] = Field(default_factory=list)
    document_id: str | None = None
    document_url: str | None = None
    summary: str = ""
