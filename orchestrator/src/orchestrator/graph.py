"""Orchestrator supervisor graph.

Three phases (Cursor / Replit style):
  1. planner — think and build an execution plan
  2. execute — run each plan step, hire specialists via the SDK
  3. ui_agent — stream the answer; rich UI only for specialist data
"""

from __future__ import annotations

import orchestrator.env  # noqa: F401 — load repo-root .env before nodes

from langgraph.graph import END, START, StateGraph

from orchestrator.nodes.execute import execute
from orchestrator.nodes.planner import planner
from orchestrator.nodes.ui_agent import ui_agent
from orchestrator.state import State

builder = (
    StateGraph(State)
    .add_node("planner", planner)
    .add_node("execute", execute)
    .add_node("ui_agent", ui_agent)
    .add_edge(START, "planner")
    .add_edge("planner", "execute")
    .add_edge("execute", "ui_agent")
    .add_edge("ui_agent", END)
)

graph = builder.compile()
graph.name = "Cognilance Orchestrator"
