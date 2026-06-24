#!/usr/bin/env python3
"""End-to-end smoke test: registry discover + orchestrator graph routes."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
import uuid
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
    "agents/python_code_writer.py",
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


async def run_graph(prompt: str, *, thread_id: str | None = None) -> dict:
    from orchestrator.graph import graph

    config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}
    return await graph.ainvoke(
        {"messages": [HumanMessage(content=prompt)]},
        config=config,
    )


def _ui_names(result: dict) -> list[str]:
    return [
        item["name"]
        for item in (result.get("ui") or [])
        if item.get("type") == "ui"
    ]


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

        print("3) Orchestrator — simple route...")
        simple = await run_graph("What is 2+2?", thread_id="smoke-simple")
        text = simple["messages"][-1].content
        print(f"   answer: {text[:120]}")
        print(f"   route: {simple.get('route')}")
        assert simple.get("route") == "simple", "expected simple route"
        assert "text-card" not in _ui_names(simple), "text-card should not be emitted"

        print("4) Orchestrator — complex route (research)...")
        research = await run_graph(
            "Research the history of transformers in machine learning",
            thread_id="smoke-complex",
        )
        msg = research["messages"][-1]
        ui = _ui_names(research)
        results = research.get("subtask_results") or []
        print(f"   text: {str(msg.content)[:120]}")
        print(f"   route: {research.get('route')}")
        print(f"   subtasks completed: {len(results)}")
        print(f"   ui: {ui}")
        assert research.get("route") == "complex", "expected complex route"
        assert len(results) >= 1, "expected subtask results"
        assert "text-card" not in ui, "text-card should not be emitted"

        print("\nAll smoke checks passed.")
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(main())
