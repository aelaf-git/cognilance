"""Build a durable board graph.

Every pipeline is the same shape::

    START -> seed -> coordinator_plan -> specialists -> coordinator_assemble -> ui_selector -> END

``seed`` injects the pipeline name and optional *preset tasks* so thin
pipelines (weekly_report, concept_note, email_followup) skip LLM planning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import core.context.env  # noqa: F401: load repo-root .env before nodes

from langgraph.graph import END, START, StateGraph

from core.runtime.checkpointer import get_checkpointer
from pipelines.coordinator_board.coordinator import coordinator_assemble, coordinator_plan
from pipelines.coordinator_board.specialists import specialists_fanout
from pipelines.shared.state import BoardTaskState, State
from pipelines.shared.ui_selector import ui_selector

PresetFn = Callable[[str], list[BoardTaskState]]


@dataclass
class BoardPipeline:
    name: str
    title: str
    preset: PresetFn | None = None

    def __post_init__(self) -> None:
        self._builder = self._build()
        self.graph: Any = None
        self._graph_no_checkpoint: Any = None

    def _seed(self, state: State) -> dict[str, Any]:
        update: dict[str, Any] = {"pipeline": self.name}
        if self.preset is not None:
            from core.models.gateway import last_user_text

            update["preset_tasks"] = self.preset(last_user_text(state.get("messages") or []))
        return update

    def _build(self) -> StateGraph:
        return (
            StateGraph(State)
            .add_node("seed", self._seed)
            .add_node("coordinator_plan", coordinator_plan)
            .add_node("specialists", specialists_fanout)
            .add_node("coordinator_assemble", coordinator_assemble)
            .add_node("ui_selector", ui_selector)
            .add_edge(START, "seed")
            .add_edge("seed", "coordinator_plan")
            .add_edge("coordinator_plan", "specialists")
            .add_edge("specialists", "coordinator_assemble")
            .add_edge("coordinator_assemble", "ui_selector")
            .add_edge("ui_selector", END)
        )

    async def init_graph(self) -> None:
        if self.graph is not None and self._graph_no_checkpoint is not None:
            return
        self._graph_no_checkpoint = self._builder.compile()
        self._graph_no_checkpoint.name = self.title
        self.graph = self._builder.compile(checkpointer=await get_checkpointer())
        self.graph.name = f"{self.title} (durable)"

    async def ensure_graph(self, *, with_checkpointer: bool = True) -> Any:
        if self.graph is None or self._graph_no_checkpoint is None:
            await self.init_graph()
        return self.graph if with_checkpointer else self._graph_no_checkpoint

    def compile_for_studio(self) -> Any:
        """Plain compiled graph for ``langgraph dev`` (Studio supplies its own checkpointer)."""
        compiled = self._builder.compile()
        compiled.name = self.title
        return compiled
