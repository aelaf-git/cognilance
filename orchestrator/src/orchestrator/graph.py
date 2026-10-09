"""Orchestrator supervisor graph — algorithm-aligned pipeline."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any

import orchestrator.env  # noqa: F401 — load repo-root .env before nodes

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from orchestrator.db import ensure_db_dir
from orchestrator.nodes.planner import planner
from orchestrator.nodes.task import task_agent
from orchestrator.nodes.thinking_node import thinking_node
from orchestrator.nodes.ui_selector import ui_selector
from orchestrator.state import State


def _route(state: State) -> str:
    return "thinking" if state.get("route") == "simple" else "task"


_builder = (
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

_checkpointer_cm: AbstractAsyncContextManager[AsyncSqliteSaver] | None = None
_checkpointer: AsyncSqliteSaver | None = None
graph: Any = None
_graph_no_checkpoint: Any = None


async def init_graph() -> None:
    """Compile graphs: chat (no checkpointer) + optional Studio (with checkpointer)."""
    global graph, _checkpointer, _checkpointer_cm, _graph_no_checkpoint
    if graph is not None and _graph_no_checkpoint is not None:
        return
    # Chat / missions: ConversationStore is memory — no orphan checkpoints.
    _graph_no_checkpoint = _builder.compile()
    _graph_no_checkpoint.name = "Cognilance Orchestrator"

    checkpoint_path = str(ensure_db_dir().parent / "checkpoints.db")
    _checkpointer_cm = AsyncSqliteSaver.from_conn_string(checkpoint_path)
    _checkpointer = await _checkpointer_cm.__aenter__()
    graph = _builder.compile(checkpointer=_checkpointer)
    graph.name = "Cognilance Orchestrator (Studio)"


async def ensure_graph(*, with_checkpointer: bool = False) -> Any:
    """Return compiled graph. Chat uses with_checkpointer=False by default."""
    if graph is None or _graph_no_checkpoint is None:
        await init_graph()
    if with_checkpointer:
        return graph
    return _graph_no_checkpoint
