"""Atlas — independent editorial manager (Cognilance + LangChain + Groq)."""

from __future__ import annotations

import asyncio
import os
import sys

from cognilance import CognilanceManager
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv()

BRIEF_SYSTEM = """You are Atlas, an editorial director.
Rewrite the user's raw notes into a clear creative brief for a copywriter.
Output only the brief, max 120 words."""


async def _groq(system: str, user: str) -> str:
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.5,
    )
    msg = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return msg.content if isinstance(msg.content, str) else str(msg.content)


async def _print_agents(manager: CognilanceManager) -> None:
    agents = await manager.discover(limit=50)
    if not agents:
        print("\n(registry empty)\n")
        return
    print()
    for a in agents:
        skills = ", ".join(s.name for s in a.skills)
        print(f"  • {a.name} [{skills}]")
    print()


async def _run(manager: CognilanceManager, notes: str) -> None:
    print(f"\n[trace {manager.trace_id}] Atlas shaping brief...\n")
    brief = await _groq(BRIEF_SYSTEM, notes)
    print(f"Brief:\n{brief}\n")

    marketers = await manager.discover(skills=["marketing"], limit=5)
    if marketers:
        target = marketers[0]
        print(f"→ Hiring copywriter: {target.name}")
        result = await manager.hire(target, input_text=brief)
        print(f"\n{result.output.text}\n")
        return

    pipelines = await manager.discover(skills=["pipeline"], limit=3)
    if pipelines:
        target = pipelines[0]
        print(f"→ Hiring pipeline delegator: {target.name}")
        result = await manager.hire(target, input_text=notes)
        print(f"\n{result.output.text}\n")
        if result.output.data.get("hired"):
            print(f"  ↳ chain: {result.output.data['hired']}")
        return

    print("No marketing agents online. Start Spark or Prism first.\n")


async def main() -> None:
    print("Atlas — Editorial Manager")
    print("Commands: agents | exit")
    print("Dashboard: http://127.0.0.1:8080/dashboard\n")

    async with CognilanceManager.from_env() as manager:
        while True:
            try:
                line = input("atlas> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                break
            if line.lower() == "agents":
                await _print_agents(manager)
                continue
            try:
                await _run(manager, line)
            except Exception as exc:
                print(f"Error: {exc}\n", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
