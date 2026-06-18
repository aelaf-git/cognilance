"""Orchestrator supervisor graph.

Routes the user's prompt to a specialist Cognilance agent (discovered and hired
through the SDK) and renders the result with a generative-UI component, or falls
back to a plain answer.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from orchestrator.nodes.general import general_input
from orchestrator.nodes.hire import code_node, data_node, research_node
from orchestrator.nodes.router import router
from orchestrator.state import State


def _route(state: State) -> str:
    return state.get("route", "general")


builder = (
    StateGraph(State)
    .add_node("router", router)
    .add_node("research", research_node)
    .add_node("dataAnalyst", data_node)
    .add_node("codeReviewer", code_node)
    .add_node("general", general_input)
    .add_edge(START, "router")
    .add_conditional_edges(
        "router",
        _route,
        ["research", "dataAnalyst", "codeReviewer", "general"],
    )
    .add_edge("research", END)
    .add_edge("dataAnalyst", END)
    .add_edge("codeReviewer", END)
    .add_edge("general", END)
)

graph = builder.compile()
graph.name = "Cognilance Orchestrator"
