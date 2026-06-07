"""Forge HR — recruiting and HR tasks."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Forge HR",
    skills=["hr-recruiting", "talent"],
    description="Helps with job descriptions, hiring, and HR advice.",
    tags=["hr"],
    port=8008,
)


@agent.on_task
async def handle(task, ctx):
    if "write" in task.input.text.lower():
        writers = await ctx.discover(skills=["content-writing"], limit=3)
        if writers:
            result = await ctx.hire(writers[0], input_text=task.input.text)
            return task.complete(text=result.output.text, data={"hired": writers[0].name})

    answer = await asyncio.to_thread(
        ask,
        "You are an HR director. Help with recruiting, job posts, and talent strategy.",
        task.input.text,
    )
    return task.complete(text=answer)


if __name__ == "__main__":
    agent.chat()
