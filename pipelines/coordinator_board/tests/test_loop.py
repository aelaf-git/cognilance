"""Graph shape and a few scripted turns through the ReAct loop."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from pipelines.coordinator_board.graph import build_graph
from pipelines.coordinator_board.models import Brief, Delegation, ThinkDecision
from tools.registry import ApprovalRequired


def _decision(**kwargs) -> ThinkDecision:
    base = {
        "user_ask": "test",
        "already_known": "",
        "missing": "",
        "next_step": "act",
        "action": "finish",
    }
    base.update(kwargs)
    return ThinkDecision(**base)


class _Script:
    def __init__(self, decisions: list[ThinkDecision]):
        self._decisions = list(decisions)

    async def __call__(self, schema, _prompt: str, temperature: float = 0.1):
        name = schema.__name__
        if name == "ThinkDecision":
            if not self._decisions:
                raise AssertionError("script ended")
            return self._decisions.pop(0)
        if name == "Verdict":
            from pipelines.coordinator_board.models import Verdict

            return Verdict(verdict="accept", reason="ok")
        if name == "ClaimSet":
            from pipelines.coordinator_board.models import ClaimSet

            return ClaimSet()
        raise AssertionError(name)


async def _invoke(decisions: list[ThinkDecision], message: str, execute: AsyncMock):
    graph = build_graph().compile()
    script = _Script(decisions)
    with (
        patch("pipelines.coordinator_board.llm_call.call_structured", script),
        patch("pipelines.coordinator_board.loop.execute_brief", execute),
        patch("pipelines.shared.ui_selector.push_ui_message", lambda *args, **kwargs: None),
    ):
        return await graph.ainvoke(
            {"messages": [HumanMessage(content=message)], "run_id": ""},
            config={"recursion_limit": 80},
        )


def test_chat_graph_is_the_react_loop():
    from pipelines.coordinator_board.graph import graph

    assert {"seed", "think", "act", "observe", "evaluate", "grounding", "ui_selector"} <= set(
        graph.nodes
    )
    assert "coordinator_plan" not in graph.nodes
    assert "specialists" not in graph.nodes


def test_preset_graph_stays_on_the_board():
    from pipelines.weekly_report.graph import graph as weekly

    assert "coordinator_plan" in weekly.nodes
    assert "specialists" in weekly.nodes
    assert "think" not in weekly.nodes


@pytest.mark.asyncio
async def test_greeting_answers_without_a_specialist():
    execute = AsyncMock()
    result = await _invoke(
        [_decision(action="answer_directly", direct_answer="Hey. What can I help with?")],
        "hey!",
        execute,
    )
    execute.assert_not_called()
    assert result["delegation_count"] == 0
    assert "Hey" in result["final_text"]


@pytest.mark.asyncio
async def test_greeting_delegation_is_refused():
    execute = AsyncMock()
    result = await _invoke(
        [
            _decision(
                action="delegate",
                delegations=[
                    Delegation(
                        agent_id="researcher",
                        brief=Brief(
                            goal="Look up a friendly reply",
                            success_criteria=["A greeting"],
                        ),
                    )
                ],
            )
        ],
        "hey!",
        execute,
    )
    execute.assert_not_called()
    assert result["delegation_count"] == 0
    assert "help" in result["final_text"].lower()


@pytest.mark.asyncio
async def test_approval_pauses_without_claiming_success():
    execute = AsyncMock(
        side_effect=ApprovalRequired("gmail.send", "send", {"to": "a@b.c"}, "irreversible")
    )
    result = await _invoke(
        [
            _decision(
                action="delegate",
                status_line="Checking whether this can be sent.",
                delegations=[
                    Delegation(
                        agent_id="email_agent",
                        brief=Brief(
                            goal="Send the note to Ada",
                            success_criteria=["The message is sent"],
                        ),
                    )
                ],
            )
        ],
        "Send the note to Ada",
        execute,
    )
    assert result["waiting_approval"] is True
    assert "gmail.send" in result["final_text"]
    assert "sent the" not in result["final_text"].lower()
