"""Run scripted orchestrator cases and summarise delegation and grounding."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from pipelines.coordinator_board.graph import build_graph
from pipelines.coordinator_board.models import (
    Brief,
    Claim,
    ClaimSet,
    Delegation,
    ThinkDecision,
    Verdict,
)


def _brief(raw: dict[str, Any]) -> Brief:
    return Brief(
        goal=str(raw.get("goal") or ""),
        context=str(raw.get("context") or ""),
        constraints=[str(item) for item in (raw.get("constraints") or [])],
        expected_output=dict(raw.get("expected_output") or {}),
        success_criteria=[str(item) for item in (raw.get("success_criteria") or [])],
        budget=str(raw.get("budget") or ""),
    )


def _decision(case: dict[str, Any], turn: dict[str, Any]) -> ThinkDecision:
    action = str(turn["action"])
    answer = str(turn.get("answer") or "")
    delegations = [
        Delegation(agent_id=str(item["agent_id"]), brief=_brief(item))
        for item in (turn.get("delegations") or [])
    ]
    return ThinkDecision(
        user_ask=str(turn.get("user_ask") or case.get("message") or "")[:200],
        already_known=str(turn.get("already_known") or ""),
        missing=str(turn.get("missing") or ""),
        next_step=str(turn.get("next_step") or action),
        action=action,  # type: ignore[arg-type]
        direct_answer=answer if action == "answer_directly" else "",
        finish_answer=answer if action == "finish" else "",
        question=str(turn.get("question") or ""),
        delegations=delegations,
        status_line=str(turn.get("status_line") or ""),
        assumption=str(turn.get("assumption") or ""),
        tool_id=str(turn.get("tool_id") or ""),
    )


def _messages(case: dict[str, Any]) -> list:
    messages = []
    for item in case.get("history") or []:
        content = str(item.get("content") or "")
        if item.get("role") == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    messages.append(HumanMessage(content=str(case.get("message") or "")))
    return messages


class _World:
    def __init__(self, case: dict[str, Any]):
        self.case = case
        self.turns = list(case.get("turns") or [])
        self.results = list(case.get("specialist_results") or [])
        self.prompts: list[str] = []
        self.executed: list[str] = []
        self.briefs: list[Brief] = []
        self.peak = 0
        self._current = 0
        self._lock = asyncio.Lock()

    async def call_structured(self, schema: type, prompt: str, temperature: float = 0.1):
        self.prompts.append(prompt)
        name = schema.__name__
        if name == "ThinkDecision":
            if not self.turns:
                raise AssertionError(f"{self.case['id']} asked for another thought")
            return _decision(self.case, self.turns.pop(0))
        if name == "Verdict":
            match = re.search(r"observation_id:\s*(\S+)", prompt)
            return Verdict(
                observation_id=match.group(1) if match else "",
                verdict=self.case.get("verdict") or "accept",
                reason="scripted",
            )
        if name == "ClaimSet":
            return self._claims(prompt)
        raise AssertionError(f"unexpected schema {name}")

    def _claims(self, prompt: str) -> ClaimSet:
        mode = str(self.case.get("claim_mode") or "none")
        if mode == "planted":
            return ClaimSet(
                claims=[
                    Claim(
                        text=str(self.case.get("planted_claim") or ""),
                        observation_ids=["missing"],
                        external=True,
                    )
                ]
            )
        if mode == "bind":
            ids = re.findall(r"id=(obs_[0-9a-f]+)", prompt)
            return ClaimSet(
                claims=[Claim(text="supported by observation", observation_ids=ids, external=True)]
            )
        return ClaimSet()

    async def execute(self, agent_id: str, brief: Brief) -> dict[str, Any]:
        self.executed.append(agent_id)
        self.briefs.append(brief)
        async with self._lock:
            self._current += 1
            self.peak = max(self.peak, self._current)
        if self.case.get("parallel"):
            await asyncio.sleep(0.05)
        async with self._lock:
            self._current -= 1
        if not self.results:
            return {"text": "", "data": {}}
        item = self.results.pop(0)
        return {"text": str(item.get("text") or ""), "data": dict(item.get("data") or {})}


def _answer(result: dict[str, Any]) -> str:
    text = str(result.get("final_text") or "")
    if text:
        return text
    messages = result.get("messages") or []
    if not messages:
        return ""
    content = messages[-1].content
    return content if isinstance(content, str) else str(content)


def _patches(case: dict[str, Any]):
    from unittest.mock import patch

    import pipelines.coordinator_board.loop as loop_mod

    active = []
    if case.get("offline"):
        offline = set(case["offline"])
        original = loop_mod.build_roster

        def wrapped():
            roster = original()
            agents = []
            for agent in roster.agents:
                if agent.id in offline:
                    agents.append(agent.model_copy(update={"status": "offline"}))
                else:
                    agents.append(agent)
            return roster.model_copy(update={"agents": agents})

        active.append(patch.object(loop_mod, "build_roster", wrapped))
    if case.get("max_iterations"):
        active.append(patch.object(loop_mod, "MAX_ITERATIONS", int(case["max_iterations"])))
    if case.get("max_delegations"):
        active.append(patch.object(loop_mod, "MAX_DELEGATIONS", int(case["max_delegations"])))
    if case.get("deadline_elapsed"):
        import time

        real = time.monotonic
        ticks = {"n": 0}

        def fake() -> float:
            ticks["n"] += 1
            base = real()
            if ticks["n"] <= 1:
                return base
            return base + 1000

        active.append(patch.object(loop_mod, "_now", fake))
    return active


async def run_case(case: dict[str, Any]) -> dict[str, Any]:
    from unittest.mock import patch

    world = _World(case)
    graph = build_graph().compile()
    patches = [
        patch("pipelines.coordinator_board.llm_call.call_structured", world.call_structured),
        patch("pipelines.coordinator_board.loop.execute_brief", world.execute),
        patch("pipelines.shared.ui_selector.push_ui_message", lambda *args, **kwargs: None),
        *_patches(case),
    ]
    for item in patches:
        item.start()
    try:
        result = await graph.ainvoke(
            {"messages": _messages(case), "run_id": ""},
            config={"recursion_limit": 80},
        )
    finally:
        for item in reversed(patches):
            item.stop()

    answer = _answer(result)
    blob = " ".join(
        str(obs.get("payload") or {})
        for obs in (result.get("observations") or [])
    )
    return {
        "id": case["id"],
        "answer": answer,
        "delegations": int(result.get("delegation_count") or 0),
        "iterations": int(result.get("iteration") or 0),
        "unsupported_remaining": int(result.get("unsupported_remaining") or 0),
        "blocked": len(result.get("blocked_claims") or []),
        "executed": list(world.executed),
        "briefs": world.briefs,
        "prompts": world.prompts,
        "peak": world.peak,
        "observations": blob,
        "waiting_approval": bool(result.get("waiting_approval")),
    }


def check_case(case: dict[str, Any], outcome: dict[str, Any]) -> None:
    expect = case.get("expect") or {}
    answer = outcome["answer"]
    lowered = answer.lower()
    if "delegations" in expect:
        assert outcome["delegations"] == expect["delegations"], outcome
    if "max_iterations" in expect:
        assert outcome["iterations"] <= int(expect["max_iterations"]), outcome
    for needle in expect.get("answer_contains") or []:
        assert needle.lower() in lowered, (needle, answer)
    for needle in expect.get("answer_forbids") or []:
        assert needle.lower() not in lowered, (needle, answer)
    if "executed" in expect:
        assert outcome["executed"] == expect["executed"], outcome["executed"]
    if expect.get("parallel"):
        assert outcome["peak"] >= 2, outcome["peak"]
    if expect.get("sequential") and len(outcome["executed"]) > 1:
        assert outcome["peak"] == 1, outcome["peak"]
    for needle in expect.get("prompt_contains") or []:
        assert any(needle in prompt for prompt in outcome["prompts"]), needle
    if expect.get("observation_contains"):
        assert expect["observation_contains"] in outcome["observations"]
    for brief in outcome["briefs"]:
        assert len(brief.goal.strip()) >= 8
        assert any(item.strip() for item in brief.success_criteria)
    assert outcome["unsupported_remaining"] == 0


def summarize(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    count = len(rows) or 1
    delegated = sum(1 for row in rows if int(row["delegations"]) > 0)
    unsupported = sum(int(row["unsupported_remaining"]) for row in rows)
    iterations = sum(int(row["iterations"]) for row in rows)
    return {
        "cases": len(rows),
        "delegation_rate": round(delegated / count, 3),
        "hallucination_rate": round(unsupported / count, 3),
        "average_iterations": round(iterations / count, 3),
        "blocked_claims": sum(int(row["blocked"]) for row in rows),
    }
