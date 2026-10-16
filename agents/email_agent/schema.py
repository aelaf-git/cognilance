from __future__ import annotations

from pydantic import BaseModel


class Result(BaseModel):
    to: str = ""
    subject: str = ""
    body: str = ""
    status: str = "draft"  # draft | sent
    message_id: str | None = None
