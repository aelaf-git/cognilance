"""Structured schemas for the specialist agent loop."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DocxBlock(BaseModel):
    """One block the Word agent can set without hand-writing JSON."""

    type: str = Field(default="paragraph", description="paragraph, heading, equation, bullet, or title")
    text: str = Field(default="", description="Block text. Equations may use _{ }, ^{ }, \\frac, and \\sqrt.")
    level: int | None = Field(default=None, description="Heading level 1-3")
    items: list[str] = Field(default_factory=list, description="Bullet or numbered items")


class DocxAction(BaseModel):
    """One step for the Word agent. Blocks are fields, not a JSON string."""

    status: Literal["call_tool", "done"] = "done"
    tool: str = Field(default="thinking", description="docx.create, docx.write, docx.style, docx.read, or thinking")
    mode: Literal["append", "insert", "replace_block", "replace", "delete"] = "append"
    document_id: str = ""
    block_id: str = Field(default="", description="Stable block id, blk_ plus 8 hex characters")
    at: int | None = Field(default=None, description="Insert position")
    index: int | None = Field(default=None, description="Block index for replace_block when no block_id is set")
    title: str = ""
    blocks: list[DocxBlock] = Field(default_factory=list)
    tool_instruction: str = Field(
        default="",
        description="JSON only for tables, charts, style, or objects the block fields cannot express",
    )
    answer: str = Field(default="", description="One short sentence when status is done")
    reasoning: str = Field(default="", description="Short rationale (not shown as answer)")


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
