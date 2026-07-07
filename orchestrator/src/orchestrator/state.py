"""Orchestrator graph state."""

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


class Subtask(TypedDict, total=False):
    id: str
    title: str
    instruction: str
    skill: str | None
    tool: str | None
    action: str | None
    params: dict[str, Any] | None
    assignee: str
    depends_on: list[str]


class SubtaskResult(TypedDict, total=False):
    subtask_id: str
    text: str
    data: dict[str, Any]
    assignee: str
    status: str


class State(TypedDict, total=False):
    """Shared state for the orchestrator graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]
    complexity: str
    route: str
    thinking: str
    plan: Plan
    catalog_agents: list[dict[str, Any]]
    catalog_text: str
    catalog_fetched_at: float | None
    subtasks: list[Subtask]
    subtask_results: list[SubtaskResult]
    final_text: str
    final_data: dict[str, Any]
    answer_streamed: bool
    direct_reply: bool
