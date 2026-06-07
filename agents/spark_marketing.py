"""Spark Marketing — marketing and campaigns."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Spark Marketing",
    skills=["marketing", "campaigns"],
    description="Creates marketing copy and campaign ideas.",
    tags=["marketing"],
    port=8007,
)


@agent.on_task
async def handle(task, ctx):
    if "research" in task.input.text.lower():
        researchers = await ctx.discover(skills=["research"], limit=3)
        if researchers:
            result = await ctx.hire(researchers[0], input_text=task.input.text)
            return task.complete(text=result.output.text, data={"hired": researchers[0].name})

    answer = await asyncio.to_thread(
        ask,
        "You are a marketing strategist. Create compelling copy and campaign ideas.",
        task.input.text,
    )
    return task.complete(text=answer)


if __name__ == "__main__":
    agent.chat()
