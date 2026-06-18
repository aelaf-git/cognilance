"""General node — a plain Groq answer for requests with no matching agent."""

from __future__ import annotations

import uuid

from langchain_core.messages import AIMessage

from orchestrator.llm import get_llm
from orchestrator.state import State

SYSTEM = (
    "You are the Cognilance orchestrator. You can hire specialist agents for "
    "research, data analysis, and code review. For anything else, answer the user "
    "directly and concisely. If relevant, mention which specialist could help."
)


async def general_input(state: State) -> dict:
    llm = get_llm(temperature=0.4)
    response = await llm.ainvoke(
        [{"role": "system", "content": SYSTEM}, *state.get("messages", [])]
    )
    return {
        "messages": [
            AIMessage(
                id=str(uuid.uuid4()),
                content=response.content
                if isinstance(response.content, str)
                else str(response.content),
            )
        ]
    }
