from __future__ import annotations

from pydantic import BaseModel


class Result(BaseModel):
    title: str = ""
    document_id: str | None = None
    style_summary: str = ""
    summary: str = ""
