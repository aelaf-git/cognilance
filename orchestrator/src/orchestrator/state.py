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
    action: str
    skill: str | None
    reasoning: str
    suggested_ui: str | None
    thinking: str
    steps: list[PlanStep]


class HireResult(TypedDict, total=False):
    mode: str
    text: str
    data: dict[str, Any]
    skill: str | None
    agent_name: str | None


class State(TypedDict, total=False):
    """Shared state for the orchestrator graph."""

    messages: Annotated[list[BaseMessage], add_messages]
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]
    plan: Plan
    hire_result: HireResult
