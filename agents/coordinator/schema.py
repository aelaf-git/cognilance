"""Structured plan produced by the coordinator."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlannedTask(BaseModel):
    title: str = Field(description="Short task title")
    instruction: str = Field(description="Self-contained instruction for the specialist")
    assignee_role: str = Field(description="Specialist id that owns this task")
    depends_on_titles: list[str] = Field(
        default_factory=list, description="Titles of tasks that must finish first"
    )


class Result(BaseModel):
    reasoning: str = Field(default="", description="Brief plan rationale")
    tasks: list[PlannedTask] = Field(default_factory=list)
    suggested_ui: str | None = Field(
        default=None, description="Optional UI hint: email-draft | research-sources | text"
    )


CoordinatorPlan = Result
