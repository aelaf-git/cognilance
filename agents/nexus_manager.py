"""Nexus Manager — discovers agents in the registry and hires the right one."""

from __future__ import annotations

import asyncio

from cognilance import CognilanceAgent
from llm import ask

agent = CognilanceAgent(
    name="Nexus Manager",
    skills=["management", "orchestration"],
    description="Views the registry and routes tasks to specialist agents.",
    tags=["manager"],
    port=8010,
)


@agent.on_task
async def handle(task, ctx):
    roster = await ctx.discover(limit=50)

    if not roster:
        answer = await asyncio.to_thread(
            ask,
            "You are a helpful assistant. Answer the user's request directly.",
            task.input.text,
        )
        return task.complete(text=answer, data={"registry_count": 0, "hired": None})

    roster_text = "\n".join(
        f"- {a.name}: {[s.name for s in a.skills]}" for a in roster
    )

    skill_pick = await asyncio.to_thread(
        ask,
        (
            "Pick the ONE best skill to handle the request. "
            "Reply with ONLY the skill name, nothing else."
        ),
        f"Request: {task.input.text}\n\nAvailable agents:\n{roster_text}",
    )
    needed_skill = skill_pick.strip().lower().replace(" ", "-")

    candidates = await ctx.discover(skills=[needed_skill], limit=5)
    if not candidates:
        for a in roster:
            if any(needed_skill in s.name for s in a.skills):
                candidates = [a]
                break

    if candidates:
        hired = candidates[0]
        result = await ctx.hire(hired, input_text=task.input.text)
        return task.complete(
            text=result.output.text,
            data={
                "registry_count": len(roster),
                "needed_skill": needed_skill,
                "hired": hired.name,
            },
        )

    answer = await asyncio.to_thread(
        ask,
        "You are a helpful assistant. Answer the user's request directly.",
        task.input.text,
    )
    return task.complete(
        text=answer,
        data={"registry_count": len(roster), "needed_skill": needed_skill, "hired": None},
    )


if __name__ == "__main__":
    agent.chat()
