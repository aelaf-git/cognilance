"""Orchestrator graph state."""

from __future__ import annotations

from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langgraph.graph.ui import AnyUIMessage, ui_message_reducer


class State(TypedDict, total=False):
    """Shared state for the orchestrator.

    - ``messages``: the running chat transcript.
    - ``ui``: generative UI messages emitted via ``push_ui_message``.
    - ``route``: the skill bucket chosen by the router node.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    ui: Annotated[Sequence[AnyUIMessage], ui_message_reducer]
    route: str
