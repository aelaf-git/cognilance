"""Byte Coder — code review specialist."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Byte Coder",
    skills=["code-review", "debugging"],
    description="Reviews code for bugs, security, and best practices.",
    tags=["engineering"],
    port=8003,
)


@agent.on_task
async def handle(task, ctx):
    answer = await asyncio.to_thread(
        ask,
        "You are a senior software engineer. Review code and give actionable feedback.",
        task.input.text,
    )
    return task.complete(text=answer)


if __name__ == "__main__":
    agent.chat()
