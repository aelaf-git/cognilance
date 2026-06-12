"""Manager — Editorial Hiring (Cognilance + LangChain + Groq)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from cognilance import CognilanceManager
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MANAGER_NAME = "Manager — Editorial"
PORT = 8020
BRIEF_SYSTEM = """You are an editorial manager on the Cognilance marketplace.
Rewrite the user's raw notes into a clear creative brief for a marketing worker.
Output only the brief, max 120 words."""


async def _groq(system: str, user: str) -> str:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.5,
    )
    msg = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return msg.content if isinstance(msg.content, str) else str(msg.content)


async def handle(manager: CognilanceManager, notes: str) -> str:
    lines = [f"[trace {manager.trace_id}] Shaping editorial brief…"]
    brief = await _groq(BRIEF_SYSTEM, notes)
    lines.append(f"Brief:\n{brief}")

    marketers = await manager.discover(skills=["marketing"], limit=5)
    if marketers:
        target = marketers[0]
        lines.append(f"→ Hiring: {target.name}")
        result = await manager.hire(target, input_text=brief)
        lines.append(result.output.text)
        return "\n\n".join(lines)

    pipelines = await manager.discover(skills=["pipeline"], limit=3)
    if pipelines:
        target = pipelines[0]
        lines.append(f"→ Hiring: {target.name}")
        result = await manager.hire(target, input_text=notes)
        lines.append(result.output.text)
        if result.output.data.get("hired"):
            lines.append(f"↳ chain: {result.output.data['hired']}")
        return "\n\n".join(lines)

    return "\n\n".join(lines + ["No marketing workers or pipeline delegators online."])


async def main() -> None:
    open_ui = "--open" in sys.argv
    async with CognilanceManager(agent_name=MANAGER_NAME) as manager:
        manager.chat(
            handle,
            description="Shapes creative briefs and hires marketing workers or launch pipelines.",
            port=PORT,
            open_ui=open_ui,
        )


if __name__ == "__main__":
    asyncio.run(main())
