"""Forge — independent engineering manager (Cognilance + LangChain + Groq)."""

from __future__ import annotations

import asyncio
import os
import sys

from cognilance import CognilanceManager
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

load_dotenv()

TRIAGE_SYSTEM = """You are Forge, an engineering manager.
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
    print(f"\n[trace {manager.trace_id}] Forge triaging submission...\n")
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
        print(f"→ Hiring engineer: {target.name}")
        result = await manager.hire(target, input_text=payload)
        print(f"\n{result.output.text}\n")
        return

    routers = await manager.discover(skills=["routing"], limit=3)
    if routers:
        target = routers[0]
        print(f"→ Hiring router delegator: {target.name}")
        result = await manager.hire(target, input_text=payload)
        print(f"\n{result.output.text}\n")
        if result.output.data.get("hired"):
            print(f"  ↳ routed to: {result.output.data['hired']}")
        return

    print("No engineering agents online. Start Byte or Nexus first.\n")


async def main() -> None:
    print("Forge — Engineering Manager")
    print("Commands: agents | exit")
    print("Dashboard: http://127.0.0.1:8080/dashboard\n")

    async with CognilanceManager.from_env() as manager:
        while True:
            try:
                line = input("forge> ").strip()
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
