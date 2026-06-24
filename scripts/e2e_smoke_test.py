#!/usr/bin/env python3
"""End-to-end smoke test: registry discover + orchestrator graph routes."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import httpx
from langchain_core.messages import HumanMessage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator" / "src"))

REGISTRY = "http://127.0.0.1:8088"
AGENT_PORTS = (8101, 8102, 8103)
AGENT_SCRIPTS = (
    "agents/research_agent.py",
    "agents/data_analyst.py",
    "agents/code_reviewer.py",
)


def wait_http(url: str, *, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=1.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}")


def start_agents() -> list[subprocess.Popen]:
    procs: list[subprocess.Popen] = []
    for script in AGENT_SCRIPTS:
        procs.append(
            subprocess.Popen(
                [sys.executable, "-u", str(ROOT / script)],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        )
    for port in AGENT_PORTS:
        wait_http(f"http://127.0.0.1:{port}/health")
    return procs


async def run_graph(prompt: str) -> dict:
    from orchestrator.graph import graph

    return await graph.ainvoke({"messages": [HumanMessage(content=prompt)]})


async def main() -> None:
    print("1) Checking registry...")
    wait_http(f"{REGISTRY}/health")
    print("   registry ok")

    print("2) Starting agents...")
    procs = start_agents()
    try:
        discover = httpx.get(f"{REGISTRY}/v1/agents/discover", params={"limit": 10}, timeout=5.0)
        discover.raise_for_status()
        agents = discover.json().get("agents", [])
        print(f"   {len(agents)} agent(s) online: {[a['name'] for a in agents]}")

        print("3) Orchestrator — general route...")
        general = await run_graph("What is 2+2?")
        text = general["messages"][-1].content
        plan = general.get("plan") or {}
        print(f"   answer: {text[:120]}")
        print(f"   plan action: {plan.get('action')}")

        print("4) Orchestrator — research route (hires Research Agent)...")
        research = await run_graph("Research the history of transformers in machine learning")
        msg = research["messages"][-1]
        ui = research.get("ui") or []
        hire = research.get("hire_result") or {}
        print(f"   text: {str(msg.content)[:120]}")
        print(f"   hired: {hire.get('agent_name')}")
        print(f"   ui messages: {len(ui)}")

        print("\nAll smoke checks passed.")
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
