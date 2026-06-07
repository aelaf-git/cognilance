"""Lyra Writer — content and copywriting."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Lyra Writer",
    skills=["content-writing", "copywriting"],
    description="Writes articles, emails, and marketing copy.",
    tags=["writing"],
    port=8004,
)


@agent.on_task
async def handle(task, ctx):
    if "translate" in task.input.text.lower():
        translators = await ctx.discover(skills=["translation"], limit=3)
        if translators:
            result = await ctx.hire(translators[0], input_text=task.input.text)
            return task.complete(text=result.output.text, data={"hired": translators[0].name})

    answer = await asyncio.to_thread(
        ask,
        "You are a professional writer. Write clear, engaging content.",
        task.input.text,
    )
    return task.complete(text=answer)


if __name__ == "__main__":
    agent.chat()
