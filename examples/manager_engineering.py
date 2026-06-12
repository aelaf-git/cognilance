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

load_dotenv()

MANAGER_NAME = "Manager — Engineering"
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


async def _run(manager: CognilanceManager, submission: str) -> None:
    print(f"\n[trace {manager.trace_id}] Triaging engineering submission...\n")
    kind = (await _groq(TRIAGE_SYSTEM, submission)).strip().lower()
    print(f"Classification: {kind}\n")

    prompt_prefix = {
        "snippet": "Code snippet review:\n",
        "architecture": "Architecture review:\n",
        "incident": "Production incident analysis:\n",
    }.get(kind, "Engineering review:\n")
    payload = prompt_prefix + submission

    coders = await manager.discover(skills=["code-review"], limit=5)
    if coders:
        target = coders[0]
        print(f"→ Hiring: {target.name}")
        result = await manager.hire(target, input_text=payload)
        print(f"\n{result.output.text}\n")
        return

    routers = await manager.discover(skills=["routing"], limit=3)
    if routers:
        target = routers[0]
        print(f"→ Hiring: {target.name}")
        result = await manager.hire(target, input_text=payload)
        print(f"\n{result.output.text}\n")
        if result.output.data.get("hired"):
            print(f"  ↳ routed to: {result.output.data['hired']}")
        return

    print("No code-review workers or router delegators online.\n")


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
                line = input("manager-engineering> ").strip()
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
