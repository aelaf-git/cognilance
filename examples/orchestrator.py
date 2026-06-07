"""Example orchestrator — CognilanceManager only, no A2A server."""

import asyncio

from cognilance import CognilanceManager


async def main() -> None:
    query = "Review this function: def add(a, b): return a + b"

    async with CognilanceManager.from_env() as manager:
        roster = await manager.discover(limit=20)
        print(f"Found {len(roster)} agents in registry")

        coders = await manager.discover(skills=["code-review"])
        if not coders:
            print("No code-review agents available.")
            return

        result = await manager.hire(coders[0], input_text=query)
        print(f"Hired: {coders[0].name}")
        print(result.output.text)


if __name__ == "__main__":
    asyncio.run(main())
