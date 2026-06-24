"""Thinking Agent — direct reasoning for simple tasks and subtask fallback."""

from __future__ import annotations

from orchestrator.llm import get_llm
from orchestrator.streaming import stream_llm

THINKING_SYSTEM = (
    "You are the Cognilance Thinking Agent. Reason clearly and answer the user "
    "directly. Be concise and accurate. Do not mention internal orchestration."
)


async def run_thinking(instruction: str, *, stream: bool = True) -> tuple[str, dict]:
    """Run the Thinking Agent on an instruction; optionally stream tokens."""
    messages = [
        {"role": "system", "content": THINKING_SYSTEM},
        {"role": "user", "content": instruction},
    ]
    if stream:
        text = await stream_llm(get_llm(temperature=0.4), messages, event="answer")
    else:
        response = await get_llm(temperature=0.4).ainvoke(messages)
        content = response.content
        text = content if isinstance(content, str) else str(content)
    return text, {"body": text}
