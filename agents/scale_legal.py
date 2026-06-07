"""Scale Legal — legal document analysis."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Scale Legal",
    skills=["legal-analysis", "compliance"],
    description="Analyzes contracts and legal documents.",
    tags=["legal"],
    port=8006,
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
        "You are a legal analyst. Explain risks, obligations, and key terms in plain language.",
        task.input.text,
    )
    return task.complete(text=answer)


if __name__ == "__main__":
    agent.chat()
