from __future__ import annotations

from pydantic import BaseModel


class Result(BaseModel):
    text: str = ""
    status: str = "draft"  # draft | posted
    post_id: str | None = None
    url: str | None = None
