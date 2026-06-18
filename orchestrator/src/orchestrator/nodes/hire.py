"""Hire nodes — discover an agent via the Cognilance SDK, hire it over A2A,
then emit a generative-UI component built from the agent's structured output.

Each route maps to a (skill, UI component) pair:

    research      -> skill "research"      -> component "research-sources"
    dataAnalyst   -> skill "data-analysis" -> component "data-chart"
    codeReviewer  -> skill "code-review"   -> component "code-findings"
"""

from __future__ import annotations

import uuid
from typing import Callable

from cognilance import CognilanceManager
from langchain_core.messages import AIMessage
from langgraph.graph.ui import push_ui_message

from orchestrator.llm import last_user_text
from orchestrator.state import State


def make_hire_node(skill: str, component: str) -> Callable[[State], object]:
    """Build a node that hires an agent with ``skill`` and renders ``component``."""

    async def node(state: State) -> dict:
        query = last_user_text(state.get("messages", []))

        async with CognilanceManager(agent_name="Orchestrator") as manager:
            agents = await manager.discover(skills=[skill], limit=5)
            if not agents:
                msg = AIMessage(
                    id=str(uuid.uuid4()),
                    content=(
                        f"No agent offering the '{skill}' skill is online right now. "
                        "Start the matching agent in /agents and try again."
                    ),
                )
                return {"messages": [msg]}

            result = await manager.hire(agents[0], input_text=query)

        message = AIMessage(id=str(uuid.uuid4()), content=result.output.text or "")
        push_ui_message(component, result.output.data or {}, message=message)
        return {"messages": [message]}

    node.__name__ = f"hire_{skill.replace('-', '_')}"
    return node


research_node = make_hire_node("research", "research-sources")
data_node = make_hire_node("data-analysis", "data-chart")
code_node = make_hire_node("code-review", "code-findings")
