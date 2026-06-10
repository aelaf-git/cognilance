"""Prism — independent multi-hop pipeline delegator (Cognilance + LangChain + Groq)."""

from __future__ import annotations

import os

from cognilance import CognilanceDelegator, CognilanceManager
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv()

PLANNER_SYSTEM = """You are Prism, a pipeline planner.
Decide if a task needs a TWO-STEP pipeline (technical review then marketing polish).
Reply with exactly one word: pipeline or direct"""

SYNTH_SYSTEM = """You are Prism. Merge technical notes and marketing copy into one cohesive deliverable."""

delegator = CognilanceDelegator(
    name="Prism",
    skills=["pipeline", "product-launch"],
    description="Chains Byte then Spark for launch-ready tech+marketing output.",
    tags=["delegator", "langchain", "groq"],
    port=8011,
)


async def _groq(system: str, user: str) -> str:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.3,
    )
    msg = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return msg.content if isinstance(msg.content, str) else str(msg.content)


@delegator.on_task
async def handle(task, manager: CognilanceManager):
    task.think("Prism deciding between pipeline vs direct hire")
    plan = (await _groq(PLANNER_SYSTEM, task.input.text)).strip().lower()
    hired: list[str] = []

    if "pipeline" in plan:
        task.think("Pipeline mode: hire Byte for technical pass")
        coders = await manager.discover(skills=["code-review"], limit=3)
        if not coders:
            return task.complete(text="Pipeline needs Byte (code-review) online.", data={"hired": []})

        tech = await manager.hire(
            coders[0],
            input_text=f"Technical review for launch:\n{task.input.text}",
        )
        hired.append(coders[0].name)
        task.think(f"Technical pass from {coders[0].name} — hiring Spark")

        marketers = await manager.discover(skills=["marketing"], limit=3)
        if not marketers:
            return task.complete(text=tech.output.text, data={"hired": hired, "partial": True})

        brief = f"Original ask:\n{task.input.text}\n\nTechnical notes:\n{tech.output.text}"
        copy = await manager.hire(marketers[0], input_text=brief)
        hired.append(marketers[0].name)
        task.think("Synthesizing pipeline output")
        final = await _groq(
            SYNTH_SYSTEM,
            f"User request:\n{task.input.text}\n\nTech:\n{tech.output.text}\n\nCopy:\n{copy.output.text}",
        )
        return task.complete(text=final, data={"hired": hired, "mode": "pipeline"})

    task.think("Direct mode: hire best marketing specialist")
    marketers = await manager.discover(skills=["marketing"], limit=3)
    if marketers:
        result = await manager.hire(marketers[0], input_text=task.input.text)
        hired.append(marketers[0].name)
        return task.complete(text=result.output.text, data={"hired": hired, "mode": "direct"})

    task.think("No marketers online — local Groq fallback")
    answer = await _groq("You are Prism, a product communications lead.", task.input.text)
    return task.complete(text=answer, data={"hired": hired, "mode": "fallback"})


if __name__ == "__main__":
    delegator.chat()
