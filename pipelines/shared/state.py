"""Orchestrator graph state: durable run + shared task board."""

from __future__ import annotations

from typing import Annotated, Any, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer


class PlanStep(TypedDict):
    title: str
    detail: str


class Plan(TypedDict, total=False):
    reasoning: str
    suggested_ui: str | None
    thinking: str
    steps: list[PlanStep]


class BoardTaskState(TypedDict, total=False):
    id: str
    title: str
    instruction: str
    assignee_role: str
    status: str
    depends_on: list[str]
    result_text: str
    result_json: dict[str, Any]


class SubtaskResult(TypedDict, total=False):
    subtask_id: str
    text: str
    data: dict[str, Any]
    assignee: str
    status: str


class PendingApproval(TypedDict, total=False):
    tool: str
    action: str | None
    params: dict[str, Any]
    risk: str
    role: str
    task_id: str | None


class Clarification(TypedDict, total=False):
    task_id: str
    role: str
    title: str
    issues: list[str]
    questions: list[str]


class State(TypedDict, total=False):
    """Shared state for the durable coordinator graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]
    run_id: str
    pipeline: str
    preset_tasks: list[BoardTaskState]
    complexity: str
    route: str
    thinking: str
    plan: Plan
    board_tasks: list[BoardTaskState]
    subtask_results: list[SubtaskResult]
    final_text: str
    final_data: dict[str, Any]
    answer_streamed: bool
    direct_reply: bool
    pending_approval: PendingApproval | None
    waiting_approval: bool
    needs_clarification: bool
    clarification: Clarification
    # ReAct loop. Optional so preset board graphs keep compiling.
    trace_id: str
    roster: dict[str, Any]
    observations: list[dict[str, Any]]
    iteration: int
    delegation_count: int
    deadline_ts: float
    verdicts: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    retries: dict[str, int]
    loop_status: str
    last_decision: dict[str, Any]
    pending_observations: list[dict[str, Any]]
    proposed_answer: str
    accepted_ids: list[str]
    retry_feedback: str
    blocked_claims: list[str]
    unsupported_remaining: int
    halt: bool
