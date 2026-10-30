"""Chat orchestrator: a bounded think-act-observe-evaluate loop.

Preset pipelines keep the linear board graph in ``pipelines.shared.build``.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from core.runtime.checkpointer import get_checkpointer
from pipelines.coordinator_board.grounding import grounding
from pipelines.coordinator_board.loop import (
    act,
    after_evaluate,
    after_think,
    evaluate,
    observe,
    seed,
    think,
)
from pipelines.shared.state import State
from pipelines.shared.ui_selector import ui_selector

RECURSION_LIMIT = 80


def build_graph() -> StateGraph:
    graph = StateGraph(State)
    graph.add_node("seed", seed)
    graph.add_node("think", think)
    graph.add_node("act", act)
    graph.add_node("observe", observe)
    graph.add_node("evaluate", evaluate)
    graph.add_node("grounding", grounding)
    graph.add_node("ui_selector", ui_selector)
    graph.add_edge(START, "seed")
    graph.add_edge("seed", "think")
    graph.add_conditional_edges("think", after_think, ["act", "grounding"])
    graph.add_edge("act", "observe")
    graph.add_edge("observe", "evaluate")
    graph.add_conditional_edges("evaluate", after_evaluate, ["think", "grounding"])
    graph.add_edge("grounding", "ui_selector")
    graph.add_edge("ui_selector", END)
    return graph


def _compile(checkpointer: Any = None) -> Any:
    compiled = build_graph().compile(checkpointer=checkpointer)
    return compiled.with_config({"recursion_limit": RECURSION_LIMIT})


class _Orchestrator:
    def __init__(self) -> None:
        self.graph: Any = None
        self._plain: Any = None

    async def init_graph(self) -> None:
        if self.graph is not None and self._plain is not None:
            return
        self._plain = _compile(None)
        self._plain.name = "Cognilance Coordinator"
        self.graph = _compile(await get_checkpointer())
        self.graph.name = "Cognilance Coordinator (durable)"

    async def ensure_graph(self, *, with_checkpointer: bool = True) -> Any:
        if self.graph is None or self._plain is None:
            await self.init_graph()
        return self.graph if with_checkpointer else self._plain

    def compile_for_studio(self) -> Any:
        compiled = _compile(None)
        compiled.name = "Cognilance Coordinator"
        return compiled


_PIPELINE = _Orchestrator()


async def init_graph() -> None:
    await _PIPELINE.init_graph()


async def ensure_graph(*, with_checkpointer: bool = True) -> Any:
    return await _PIPELINE.ensure_graph(with_checkpointer=with_checkpointer)


graph = _PIPELINE.compile_for_studio()
