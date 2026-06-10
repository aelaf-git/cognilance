"""Nexus — independent single-hop delegator (Cognilance + LangChain + Groq)."""

from __future__ import annotations

import os

from cognilance import CognilanceDelegator, CognilanceManager
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv()

ROUTER_SYSTEM = """You are Nexus, a marketplace router.
Reply with exactly ONE skill tag and nothing else:
code-review
marketing"""

FALLBACK_SYSTEM = """You are Nexus. Answer the user when no specialist is online."""

delegator = CognilanceDelegator(
    name="Nexus",
    skills=["routing", "orchestration"],
    description="Routes each task to one specialist on the marketplace.",
    tags=["delegator", "langchain", "groq"],
    port=8010,
)


async def _groq(system: str, user: str) -> str:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.1,
    )
    msg = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return msg.content if isinstance(msg.content, str) else str(msg.content)


@delegator.on_task
async def handle(task, manager: CognilanceManager):
    task.think("Nexus classifying task for single specialist hire")
    raw = (await _groq(ROUTER_SYSTEM, task.input.text)).strip().lower()
    skill = "marketing" if "market" in raw or "copy" in raw or "social" in raw else "code-review"

    task.think(f"Discovering agents with skill: {skill}")
    agents = await manager.discover(skills=[skill], limit=5)
    if not agents:
        task.think("No specialist online — answering directly")
        answer = await _groq(FALLBACK_SYSTEM, task.input.text)
        return task.complete(text=answer, data={"hired": None, "skill": skill})

    chosen = agents[0]
    task.think(f"Hiring {chosen.name}")
    result = await manager.hire(chosen, input_text=task.input.text)
    return task.complete(
        text=result.output.text,
        data={"hired": chosen.name, "skill": skill, "trace_id": manager.trace_id},
    )


if __name__ == "__main__":
    delegator.chat()
