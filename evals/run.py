"""Minimal eval runner: ``cognilance-evals [agent ...] [--live]``.

Each ``evals/<agent>/cases.yaml`` lists cases::

    - id: short_summary
      instruction: "Summarise ..."
      expect:
        tool: thinking              # tool the specialist should pick
        contains: ["Highlights"]    # substrings expected in result text (live only)

Offline mode (default) checks tool selection and manifest permissions only, so
it runs in CI without credentials. ``--live`` executes the specialist through
the real tool path and checks ``contains``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

EVALS_DIR = Path(__file__).resolve().parent


@dataclass
class CaseResult:
    agent: str
    case_id: str
    passed: bool
    detail: str = ""


def load_cases(agent: str) -> list[dict[str, Any]]:
    path = EVALS_DIR / agent / "cases.yaml"
    if not path.is_file():
        return []
    return list(yaml.safe_load(path.read_text()) or [])


def available_agents() -> list[str]:
    return sorted(p.parent.name for p in EVALS_DIR.glob("*/cases.yaml"))


def _check_offline(agent: str, case: dict[str, Any]) -> CaseResult:
    from agents.loader import get_role
    from pipelines.coordinator_board.specialists import _pick_tool
    from tools.registry import is_allowed

    pack = get_role(agent)
    if pack is None:
        return CaseResult(agent, case["id"], False, "unknown agent")
    tool = _pick_tool(pack.id, str(case.get("instruction") or ""), pack.tools)
    expect = case.get("expect") or {}
    want = expect.get("tool")
    if not is_allowed(pack.tools, tool):
        return CaseResult(agent, case["id"], False, f"picked {tool} not allowed for {agent}")
    if want and tool != want:
        return CaseResult(agent, case["id"], False, f"picked {tool}, expected {want}")
    return CaseResult(agent, case["id"], True, f"tool={tool}")


async def _check_live(agent: str, case: dict[str, Any]) -> CaseResult:
    from agents.loader import get_role
    from pipelines.coordinator_board.specialists import _pick_tool
    from tools.registry import run_tool

    pack = get_role(agent)
    if pack is None:
        return CaseResult(agent, case["id"], False, "unknown agent")
    instruction = str(case.get("instruction") or "")
    tool = _pick_tool(pack.id, instruction, pack.tools)
    try:
        out = await run_tool(pack, tool, instruction=instruction)
    except Exception as exc:
        return CaseResult(agent, case["id"], False, f"{tool} raised {exc}")
    text = str(out.get("text") or "")
    missing = [s for s in (case.get("expect") or {}).get("contains", []) if s.lower() not in text.lower()]
    if missing:
        return CaseResult(agent, case["id"], False, f"missing {missing}")
    return CaseResult(agent, case["id"], True, f"tool={tool} chars={len(text)}")


async def run(agents: list[str], *, live: bool) -> list[CaseResult]:
    results: list[CaseResult] = []
    for agent in agents:
        for case in load_cases(agent):
            results.append(await _check_live(agent, case) if live else _check_offline(agent, case))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cognilance-evals")
    parser.add_argument("agents", nargs="*", help="agent ids (default: all with cases.yaml)")
    parser.add_argument("--live", action="store_true", help="execute tools (needs API keys)")
    args = parser.parse_args(argv)

    agents = args.agents or available_agents()
    results = asyncio.run(run(agents, live=args.live))
    failed = [r for r in results if not r.passed]
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        print(f"{mark} {r.agent}/{r.case_id}: {r.detail}")
    print(f"\n{len(results) - len(failed)}/{len(results)} passed ({'live' if args.live else 'offline'})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
