"""Structured decisions, briefs, observations, and verdicts for the coordinator loop."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ActionName = Literal["answer_directly", "use_tool", "delegate", "ask_user", "finish"]
ObservationStatus = Literal["ok", "error", "empty", "partial"]
VerdictName = Literal["accept", "retry", "reroute", "ask_user", "fail_honestly"]
AgentStatus = Literal["available", "degraded", "offline"]


class Brief(BaseModel):
    """Task handed to one specialist. Relevant context only, never the whole chat."""

    goal: str = ""
    context: str = ""
    constraints: list[str] = Field(default_factory=list)
    expected_output: dict[str, Any] = Field(default_factory=dict)
    success_criteria: list[str] = Field(default_factory=list)
    budget: str = ""


class Delegation(BaseModel):
    agent_id: str = ""
    brief: Brief = Field(default_factory=Brief)


class ThinkDecision(BaseModel):
    """One private reasoning step and exactly one action."""

    user_ask: str = Field(default="", description="What the user is asking, in one sentence")
    already_known: str = Field(default="", description="Facts already in the conversation or observations")
    missing: str = Field(default="", description="What is still missing")
    next_step: str = Field(default="", description="The cheapest reliable next step")
    action: ActionName = "finish"
    direct_answer: str = Field(default="", description="Used when action is answer_directly")
    tool_id: str = Field(default="", description="Orchestrator tool id when action is use_tool")
    tool_instruction: str = ""
    delegations: list[Delegation] = Field(default_factory=list)
    question: str = Field(default="", description="One question when action is ask_user")
    finish_answer: str = Field(default="", description="User-facing answer when action is finish")
    assumption: str = Field(default="", description="Stated default, when one was safe to assume")
    status_line: str = Field(
        default="",
        description="Optional short status for the user during slow work. No internal ids.",
    )


class Observation(BaseModel):
    id: str
    source: str
    status: ObservationStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str


class Verdict(BaseModel):
    observation_id: str = ""
    verdict: VerdictName
    reason: str = ""
    feedback: str = ""
    question: str = ""


class Claim(BaseModel):
    text: str = ""
    observation_ids: list[str] = Field(default_factory=list)
    external: bool = False


class ClaimSet(BaseModel):
    claims: list[Claim] = Field(default_factory=list)


class RosterEntry(BaseModel):
    id: str
    description: str = ""
    required_inputs: list[str] = Field(default_factory=list)
    output_shape: dict[str, str] = Field(default_factory=dict)
    limits: str = ""
    status: AgentStatus = "available"


class Roster(BaseModel):
    agents: list[RosterEntry] = Field(default_factory=list)
    not_available: list[str] = Field(default_factory=list)
