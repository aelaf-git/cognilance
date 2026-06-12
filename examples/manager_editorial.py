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
    print(f"\n[trace {manager.trace_id}] Shaping editorial brief...\n")
    brief = await _groq(BRIEF_SYSTEM, notes)
    print(f"Brief:\n{brief}\n")

    marketers = await manager.discover(skills=["marketing"], limit=5)
    if marketers:
        target = marketers[0]
        print(f"→ Hiring: {target.name}")
        result = await manager.hire(target, input_text=brief)
        print(f"\n{result.output.text}\n")
        return

    pipelines = await manager.discover(skills=["pipeline"], limit=3)
    if pipelines:
        target = pipelines[0]
        print(f"→ Hiring: {target.name}")
        result = await manager.hire(target, input_text=notes)
        print(f"\n{result.output.text}\n")
        if result.output.data.get("hired"):
            print(f"  ↳ chain: {result.output.data['hired']}")
        return

    print("No marketing workers or pipeline delegators online.\n")


async def main() -> None:
    print(f"{MANAGER_NAME}")
    print("Managers do NOT register on the registry.")
    print("You appear on the dashboard Managers tab after you send a task.")
    print("Start workers/delegators first (separate terminals) — they fill Workers/Delegators tabs.")
    print("Commands: agents | exit")
    print("Dashboard: http://127.0.0.1:8080/dashboard\n")

    async with CognilanceManager(agent_name=MANAGER_NAME) as manager:
        while True:
            try:
                line = input("manager-editorial> ").strip()
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
