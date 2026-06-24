"""Orchestrator supervisor graph.

Two internal agents:
  1. planner — discovers registry agents, plans hires, executes them via the SDK
  2. ui_agent — chooses and emits generative UI for the result
"""

from __future__ import annotations

import orchestrator.env  # noqa: F401 — load repo-root .env before nodes

from langgraph.graph import END, START, StateGraph

from orchestrator.nodes.planner import planner
from orchestrator.nodes.ui_agent import ui_agent
from orchestrator.state import State

builder = (
    StateGraph(State)
    .add_node("planner", planner)
    .add_node("ui_agent", ui_agent)
    .add_edge(START, "planner")
    .add_edge("planner", "ui_agent")
    .add_edge("ui_agent", END)
)

graph = builder.compile()
graph.name = "Cognilance Orchestrator"
