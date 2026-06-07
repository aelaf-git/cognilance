"""Pulse Support — customer support specialist."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Pulse Support",
    skills=["customer-support", "troubleshooting"],
    description="Handles customer issues with empathy and clear solutions.",
    tags=["support"],
    port=8009,
)


@agent.on_task
async def handle(task, ctx):
    if any(kw in task.input.text.lower() for kw in ("code", "bug", "error")):
        coders = await ctx.discover(skills=["code-review"], limit=3)
        if coders:
            result = await ctx.hire(coders[0], input_text=task.input.text)
            return task.complete(text=result.output.text, data={"hired": coders[0].name})

    answer = await asyncio.to_thread(
        ask,
        "You are a customer support lead. Respond with empathy and clear solutions.",
        task.input.text,
    )
    return task.complete(text=answer)


if __name__ == "__main__":
    agent.chat()
