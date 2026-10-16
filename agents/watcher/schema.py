from __future__ import annotations

from pydantic import BaseModel, Field


class Alert(BaseModel):
    kind: str
    summary: str
    severity: str = "info"  # info | warning | critical


class Result(BaseModel):
    alerts: list[Alert] = Field(default_factory=list)
    note: str = ""
