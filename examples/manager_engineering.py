"""Manager — Engineering Hiring (Cognilance + LangChain + Groq)."""

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

MANAGER_NAME = "Manager — Engineering"
PORT = 8021
TRIAGE_SYSTEM = """You are an engineering manager on the Cognilance marketplace.
Classify the submission as: snippet, architecture, or incident.
Reply with one word only."""


async def _groq(system: str, user: str) -> str:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.2,
    )
    msg = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return msg.content if isinstance(msg.content, str) else str(msg.content)


async def handle(manager: CognilanceManager, submission: str) -> str:
    lines = [f"[trace {manager.trace_id}] Triaging engineering submission…"]
    kind = (await _groq(TRIAGE_SYSTEM, submission)).strip().lower()
    lines.append(f"Classification: {kind}")

    prompt_prefix = {
        "snippet": "Code snippet review:\n",
        "architecture": "Architecture review:\n",
        "incident": "Production incident analysis:\n",
    }.get(kind, "Engineering review:\n")
    payload = prompt_prefix + submission

    coders = await manager.discover(skills=["code-review"], limit=5)
    if coders:
        target = coders[0]
        lines.append(f"→ Hiring: {target.name}")
        result = await manager.hire(target, input_text=payload)
        lines.append(result.output.text)
        return "\n\n".join(lines)

    routers = await manager.discover(skills=["routing"], limit=3)
    if routers:
        target = routers[0]
        lines.append(f"→ Hiring: {target.name}")
        result = await manager.hire(target, input_text=payload)
        lines.append(result.output.text)
        if result.output.data.get("hired"):
            lines.append(f"↳ routed to: {result.output.data['hired']}")
        return "\n\n".join(lines)

    return "\n\n".join(lines + ["No code-review workers or router delegators online."])


async def main() -> None:
    open_ui = "--open" in sys.argv
    async with CognilanceManager(agent_name=MANAGER_NAME) as manager:
        manager.chat(
            handle,
            description="Triages engineering work and hires code-review workers or routers.",
            port=PORT,
            open_ui=open_ui,
        )


if __name__ == "__main__":
    asyncio.run(main())
