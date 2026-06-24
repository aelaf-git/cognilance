"""Orchestrator supervisor graph — algorithm-aligned pipeline."""

from __future__ import annotations

import orchestrator.env  # noqa: F401 — load repo-root .env before nodes

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from orchestrator.nodes.planner import planner
from orchestrator.nodes.task import task_agent
from orchestrator.nodes.thinking_node import thinking_node
from orchestrator.nodes.ui_selector import ui_selector
from orchestrator.state import State


def _route(state: State) -> str:
    return "thinking" if state.get("route") == "simple" else "task"


builder = (
    StateGraph(State)
    .add_node("planner", planner)
    .add_node("thinking", thinking_node)
    .add_node("task", task_agent)
    .add_node("ui_selector", ui_selector)
    .add_edge(START, "planner")
    .add_conditional_edges(
        "planner",
        _route,
        ["thinking", "task"],
    )
    .add_edge("thinking", "ui_selector")
    .add_edge("task", "ui_selector")
    .add_edge("ui_selector", END)
)

graph = builder.compile(checkpointer=MemorySaver())
graph.name = "Cognilance Orchestrator"
