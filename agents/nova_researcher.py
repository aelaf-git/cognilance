"""Nova Researcher — research and summarization."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Nova Researcher",
    skills=["research", "summarization"],
    description="Researches topics and summarizes findings.",
    tags=["research"],
    port=8002,
)


@agent.on_task
async def handle(task, ctx):
    if any(kw in task.input.text.lower() for kw in ("write", "draft", "article")):
        writers = await ctx.discover(skills=["content-writing"], limit=3)
        if writers:
            result = await ctx.hire(writers[0], input_text=task.input.text)
            return task.complete(text=result.output.text, data={"hired": writers[0].name})

    answer = await asyncio.to_thread(
        ask,
        "You are a research analyst. Provide clear, well-structured research summaries.",
        task.input.text,
    )
    return task.complete(text=answer)


if __name__ == "__main__":
    agent.chat()
