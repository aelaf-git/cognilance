"""Atlas Translator — translation specialist."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Atlas Translator",
    skills=["translation", "multilingual"],
    description="Translates text between languages.",
    tags=["nlp"],
    port=8001,
)


@agent.on_task
async def handle(task, ctx):
    if "legal" in task.input.text.lower():
        helpers = await ctx.discover(skills=["legal-analysis"], limit=3)
        if helpers:
            result = await ctx.hire(helpers[0], input_text=task.input.text)
            return task.complete(text=result.output.text, data={"hired": helpers[0].name})

    answer = await asyncio.to_thread(
        ask,
        "You are a professional translator. Translate clearly and accurately.",
        task.input.text,
    )
    return task.complete(text=answer)


if __name__ == "__main__":
    agent.chat()
