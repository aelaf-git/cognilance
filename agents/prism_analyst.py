"""Prism Analyst — data analysis specialist."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Prism Analyst",
    skills=["data-analysis", "statistics"],
    description="Analyzes data and extracts insights.",
    tags=["analytics"],
    port=8005,
)


@agent.on_task
async def handle(task, ctx):
    answer = await asyncio.to_thread(
        ask,
        "You are a data analyst. Analyze metrics, find trends, and give recommendations.",
        task.input.text,
    )
    return task.complete(text=answer)


if __name__ == "__main__":
    agent.chat()
