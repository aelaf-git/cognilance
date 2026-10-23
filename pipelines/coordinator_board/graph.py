"""Durable coordinator graph: board-centric specialists (no registry)."""

from __future__ import annotations

from typing import Any

from pipelines.shared.build import BoardPipeline

PIPELINE = BoardPipeline(name="coordinator_board", title="Cognilance Coordinator")


async def init_graph() -> None:
    await PIPELINE.init_graph()


async def ensure_graph(*, with_checkpointer: bool = True) -> Any:
    return await PIPELINE.ensure_graph(with_checkpointer=with_checkpointer)


# For LangGraph Studio / langgraph.json
graph = PIPELINE.compile_for_studio()
