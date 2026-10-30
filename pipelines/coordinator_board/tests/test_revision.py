"""A miss goes back to the same agent until the goal is met or the budget is gone."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from pipelines.coordinator_board.evidence import evidence_text
from pipelines.coordinator_board.execute import format_brief
from pipelines.coordinator_board.graph import build_graph
from pipelines.coordinator_board.grounding import _claim_prompt
from pipelines.coordinator_board.loop import (
    MAX_ITERATIONS,
    _fence,
    _judge_prompt,
    evaluate,
)
from pipelines.coordinator_board.models import Brief, Delegation, ThinkDecision, Verdict


def _paragraph(number: int) -> str:
    return f"Paragraph {number} " + ("alpha " * 500) + f"ending-{number}."


def _long_payload() -> dict:
    blocks = [{"type": "paragraph", "text": _paragraph(number)} for number in range(1, 5)]
    return {"text": "Created the document.", "data": {"blocks": blocks}, "tool": "docx.create"}


def _decision(**kwargs) -> ThinkDecision:
    base = {
        "user_ask": "Write four paragraphs about Stephen Hawking",
        "already_known": "",
        "missing": "",
        "next_step": "delegate",
        "action": "delegate",
        "delegations": [
            Delegation(
                agent_id="docx_agent",
                brief=Brief(
                    goal="Write four paragraphs about Stephen Hawking",
                    success_criteria=["Four coherent paragraphs"],
                ),
            )
        ],
    }
    base.update(kwargs)
    return ThinkDecision(**base)


def _obs(obs_id: str, payload: dict | None = None, *, status: str = "ok", source: str = "docx_agent") -> dict:
    return {
        "id": obs_id,
        "source": source,
        "status": status,
        "payload": payload if payload is not None else {"text": "Draft.", "data": {"blocks": []}},
    }


def _state(observations: list[dict], *, iteration: int = 1, verdicts: list | None = None) -> dict:
    return {
        "iteration": iteration,
        "deadline_ts": time.monotonic() + 60,
        "observations": observations,
        "last_decision": _decision().model_dump(),
        "verdicts": list(verdicts or []),
        "retries": {},
        "accepted_ids": [],
        "loop_status": "continue",
        "halt": False,
    }


def test_revision_brief_says_to_read_the_file_not_the_summary():
    from pipelines.coordinator_board.loop import _decision_from_revision

    decision = _decision_from_revision(
        {
            "agent_id": "docx_agent",
            "goal": "Write four paragraphs about Stephen Hawking",
            "success_criteria": ["Four coherent paragraphs"],
            "feedback": "Add the fourth paragraph.",
            "evidence": "open='Paragraph 1' close='ending-1.'",
        }
    )
    context = decision.delegations[0].brief.context
    assert "Read the open file" in context
    assert "Do not paste the summary" in context
    assert "Add the fourth paragraph." in context
    assert "ending-1." in context


def test_long_result_keeps_every_part_in_view():
    payload = _long_payload()
    raw = json.dumps(payload)
    assert len(raw) > 2000
    assert "Paragraph 4" not in raw[:2000]
    assert "ending-4" not in raw[:2000]

    obs = _obs("obs_bio", payload)
    decision = _decision()
    shown = [
        _judge_prompt(obs, decision),
        _fence([obs]),
        _claim_prompt("The biography is ready.", [obs]),
    ]
    for text in shown:
        assert "Paragraph 4" in text
        assert "ending-4" in text

    email = ("Hello. " * 400) + "The closing line is about the launch date."
    assert "launch date." in evidence_text({"text": email})
    assert len(evidence_text({"text": email})) < len(email)


class _Script:
    def __init__(self, decisions: list[ThinkDecision], verdicts: list[Verdict]):
        self._decisions = list(decisions)
        self._verdicts = list(verdicts)

    async def __call__(self, schema, _prompt: str, temperature: float = 0.1):
        name = schema.__name__
        if name == "ThinkDecision":
            if not self._decisions:
                raise AssertionError("script ended")
            return self._decisions.pop(0)
        if name == "Verdict":
            if not self._verdicts:
                raise AssertionError("verdict script ended")
            return self._verdicts.pop(0)
        if name == "ClaimSet":
            from pipelines.coordinator_board.models import ClaimSet

            return ClaimSet()
        raise AssertionError(name)


@pytest.mark.asyncio
async def test_retry_sends_the_same_agent_back_with_notes():
    execute = AsyncMock(
        side_effect=[
            {"text": "Draft biography.", "data": {"blocks": [{"type": "paragraph", "text": "One."}]}, "tool": "docx.create"},
            {"text": "Revised biography.", "data": {"blocks": [{"type": "paragraph", "text": "Two."}]}, "tool": "docx.write"},
            {"text": "Finished biography.", "data": {"blocks": [{"type": "paragraph", "text": "Four."}]}, "tool": "docx.write"},
        ]
    )
    script = _Script(
        [
            _decision(),
            _decision(action="finish", delegations=[], finish_answer="The biography is ready."),
        ],
        [
            Verdict(
                verdict="retry",
                reason="Missing the fourth paragraph.",
                feedback="Add the fourth paragraph.",
            ),
            Verdict(
                verdict="fail_honestly",
                reason="The fourth paragraph is still missing.",
            ),
            Verdict(verdict="accept", reason="ok"),
        ],
    )
    graph = build_graph().compile()
    with (
        patch("pipelines.coordinator_board.llm_call.call_structured", script),
        patch("pipelines.coordinator_board.loop.execute_brief", execute),
        patch("pipelines.shared.ui_selector.push_ui_message", lambda *args, **kwargs: None),
    ):
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="Create a four paragraph biography of Stephen Hawking.")],
                "run_id": "",
            },
            config={"recursion_limit": 80},
        )

    assert execute.await_count == 3
    assert [call.args[0] for call in execute.await_args_list] == ["docx_agent", "docx_agent", "docx_agent"]
    second = execute.await_args_list[1].args[1]
    third = execute.await_args_list[2].args[1]
    assert "Add the fourth paragraph" in second.context
    assert "Add the fourth paragraph" in format_brief(second)
    assert "The fourth paragraph is still missing." in third.context
    assert second.success_criteria == ["Four coherent paragraphs"]
    assert "couldn't finish" not in result["final_text"].lower()
    assert "ready" in result["final_text"].lower()


@pytest.mark.asyncio
async def test_second_quality_miss_still_revises():
    first_obs = _obs("obs_1")
    second_obs = _obs("obs_2")
    verdicts = [
        Verdict(verdict="fail_honestly", reason="Paragraph 3 stops mid-sentence."),
        Verdict(verdict="fail_honestly", reason="The fourth paragraph is still missing."),
    ]

    async def judge(_schema, _prompt, _temperature=0):
        return verdicts.pop(0)

    with patch("pipelines.coordinator_board.llm_call.call_structured", judge):
        first = await evaluate(_state([first_obs], iteration=1))
        second = await evaluate(
            _state(
                [first_obs, second_obs],
                iteration=2,
                verdicts=first["verdicts"],
            )
        )

    assert first["loop_status"] == "continue"
    assert first["revision"]["agent_id"] == "docx_agent"
    assert "mid-sentence" in first["revision"]["feedback"]
    assert second["loop_status"] == "continue"
    assert second["revision"]["agent_id"] == "docx_agent"
    assert "fourth paragraph" in second["revision"]["feedback"]
    assert "couldn't finish" not in str(second.get("proposed_answer") or "")


@pytest.mark.asyncio
async def test_quality_miss_stops_only_when_the_budget_is_gone():
    verdict = Verdict(verdict="fail_honestly", reason="The fourth paragraph is missing.")

    async def judge(_schema, _prompt, _temperature=0):
        return verdict

    with patch("pipelines.coordinator_board.llm_call.call_structured", judge):
        update = await evaluate(_state([_obs("obs_1")], iteration=MAX_ITERATIONS))

    assert update["loop_status"] == "finish"
    assert update["revision"] == {}
    assert "couldn't finish" in update["proposed_answer"].lower()
    assert "fourth paragraph" in update["proposed_answer"].lower()


@pytest.mark.asyncio
async def test_hard_error_is_not_sent_back_for_revision():
    async def judge(_schema, _prompt, _temperature=0):
        raise AssertionError("judge should not run")

    obs = _obs(
        "obs_err",
        {"error": "no such agent", "text": ""},
        status="error",
        source="orchestrator",
    )
    with patch("pipelines.coordinator_board.llm_call.call_structured", judge):
        update = await evaluate(_state([obs]))

    assert update["loop_status"] == "continue"
    assert update["revision"] == {}
    assert update["verdicts"][-1]["verdict"] == "reroute"
    assert update["verdicts"][-1]["reason"] == "no such agent"
