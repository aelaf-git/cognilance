"""Structured schemas for the specialist agent loop."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SpecialistAction(BaseModel):
    """One step of a specialist observe→act loop."""

    status: Literal["call_tool", "done"] = "done"
    tool: str = Field(default="thinking", description="Tool id when status is call_tool")
    tool_instruction: str = Field(
        default="",
        description="Focused instruction/query for the chosen tool",
    )
    answer: str = Field(
        default="",
        description="Final user-facing result for this task when status is done",
    )
    reasoning: str = Field(default="", description="Short rationale (not shown as answer)")


class VerificationResult(BaseModel):
    """Outcome of verifying one specialist task output."""

    passed: bool = Field(description="True only when the output is fit to ship")
    issues: list[str] = Field(
        default_factory=list,
        description="Concrete problems found (empty when passed)",
    )
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask the user when not passed",
    )
    reasoning: str = Field(default="", description="Brief verifier rationale")
