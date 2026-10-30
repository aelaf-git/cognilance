"""Unit tests for per-specialist verification (hard fail → clarify)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from pipelines.coordinator_board.schema import VerificationResult
from pipelines.coordinator_board.verify import (
    format_clarification_message,
    verify_task_output,
)


def _pack(**kwargs):
    defaults = dict(
        id="researcher",
        name="Researcher",
        instructions="Gather facts.",
        tools=("web.search", "link_validate.check", "thinking"),
        skills=(),
        model="default",
        prompts={"system": "Gather facts. Cite sources."},
        schema_path=None,
        path=None,
        description="research",
    )
    defaults.update(kwargs)
    pack = SimpleNamespace(**defaults)
    pack.prompt = lambda key="system": pack.prompts.get(key) or pack.instructions
    return pack


@pytest.mark.asyncio
async def test_empty_output_fails_without_llm():
    with patch(
        "pipelines.coordinator_board.verify.get_structured_llm",
    ) as get_llm:
        result = await verify_task_output(
            _pack(),
            instruction="Reply hello",
            text="   ",
            data={},
        )
    assert result.passed is False
    assert result.issues
    assert result.clarifying_questions
    get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_data_error_fails_without_llm():
    result = await verify_task_output(
        _pack(),
        instruction="Do the thing",
        text="partial",
        data={"error": "timeout"},
    )
    assert result.passed is False
    assert any("timeout" in i for i in result.issues)


@pytest.mark.asyncio
async def test_llm_pass():
    fake = MagicMock()
    fake.ainvoke = AsyncMock(
        return_value=VerificationResult(passed=True, reasoning="ok")
    )
    with (
        patch(
            "pipelines.coordinator_board.verify.get_structured_llm",
            return_value=fake,
        ),
        patch(
            "pipelines.coordinator_board.verify.coordinator",
            return_value=SimpleNamespace(prompts={"verify": "Verify carefully."}),
        ),
    ):
        result = await verify_task_output(
            _pack(),
            instruction="Say hi",
            text="Hello!",
            data={},
        )
    assert result.passed is True


@pytest.mark.asyncio
async def test_llm_error_fail_closed():
    with (
        patch(
            "pipelines.coordinator_board.verify.get_structured_llm",
            side_effect=RuntimeError("no key"),
        ),
        patch(
            "pipelines.coordinator_board.verify.coordinator",
            return_value=SimpleNamespace(prompts={"verify": "Verify."}),
        ),
    ):
        result = await verify_task_output(
            _pack(),
            instruction="Say hi",
            text="Hello!",
            data={},
        )
    assert result.passed is False
    assert any("verify" in i.lower() for i in result.issues)


@pytest.mark.asyncio
async def test_broken_links_fail_researcher():
    with patch(
        "pipelines.coordinator_board.verify.validate_links",
        new_callable=AsyncMock,
        return_value={
            "links": [
                {"url": "https://broken.example", "verdict": "broken", "note": "404"},
            ],
            "broken": 1,
            "ok": 0,
            "warning": 0,
        },
    ):
        result = await verify_task_output(
            _pack(),
            instruction="research the latest news and cite sources",
            text="See https://broken.example for details.",
            data={},
        )
    assert result.passed is False
    assert any("unreachable" in i.lower() or "broken" in i.lower() for i in result.issues)


@pytest.mark.asyncio
async def test_run_specialist_sets_clarification_on_verify_fail():
    from pipelines.coordinator_board.specialists import _run_specialist

    pack = _pack(id="researcher", name="Researcher")
    state = {
        "run_id": "",
        "messages": [HumanMessage(content="find X")],
        "board_tasks": [
            {
                "id": "t1",
                "title": "Research",
                "instruction": "research topic X",
                "assignee_role": "researcher",
                "status": "open",
            }
        ],
        "subtask_results": [],
    }
    with (
        patch("pipelines.coordinator_board.specialists.get_role", return_value=pack),
        patch(
            "pipelines.coordinator_board.specialists._run_task_loop",
            new_callable=AsyncMock,
            return_value={"text": "unclear answer", "data": {}, "tool": "thinking"},
        ),
        patch(
            "pipelines.coordinator_board.specialists.verify_task_output",
            new_callable=AsyncMock,
            return_value=VerificationResult(
                passed=False,
                issues=["Missing topic scope."],
                clarifying_questions=["Which aspect of X?"],
            ),
        ),
    ):
        update = await _run_specialist(state, "researcher")
    assert update.get("needs_clarification") is True
    assert update["clarification"]["questions"] == ["Which aspect of X?"]
    assert update.get("subtask_results") == []


@pytest.mark.asyncio
async def test_run_specialist_completes_when_verify_passes():
    from pipelines.coordinator_board.specialists import _run_specialist

    pack = _pack()
    state = {
        "run_id": "",
        "messages": [HumanMessage(content="hi")],
        "board_tasks": [
            {
                "id": "t1",
                "title": "Reply",
                "instruction": "Say hello",
                "assignee_role": "researcher",
                "status": "open",
            }
        ],
        "subtask_results": [],
    }
    with (
        patch("pipelines.coordinator_board.specialists.get_role", return_value=pack),
        patch(
            "pipelines.coordinator_board.specialists._run_task_loop",
            new_callable=AsyncMock,
            return_value={"text": "Hello!", "data": {}, "tool": "thinking"},
        ),
        patch(
            "pipelines.coordinator_board.specialists.verify_task_output",
            new_callable=AsyncMock,
            return_value=VerificationResult(passed=True),
        ),
    ):
        update = await _run_specialist(state, "researcher")
    assert not update.get("needs_clarification")
    assert len(update.get("subtask_results") or []) == 1
    assert update["subtask_results"][0]["text"] == "Hello!"


@pytest.mark.asyncio
async def test_fanout_stops_after_clarification():
    from pipelines.coordinator_board.specialists import specialists_fanout

    roles = [
        SimpleNamespace(id="researcher"),
        SimpleNamespace(id="email_agent"),
    ]
    calls: list[str] = []

    async def fake_run(state, role_id):
        calls.append(role_id)
        if role_id == "researcher":
            return {
                "subtask_results": [],
                "needs_clarification": True,
                "clarification": {
                    "task_id": "t1",
                    "role": "researcher",
                    "title": "R",
                    "issues": ["vague"],
                    "questions": ["What topic?"],
                },
            }
        return {"subtask_results": [{"subtask_id": "x", "text": "should not run"}]}

    with (
        patch("pipelines.coordinator_board.specialists.SPECIALISTS", roles),
        patch(
            "pipelines.coordinator_board.specialists._run_specialist",
            side_effect=fake_run,
        ),
    ):
        out = await specialists_fanout(
            {"messages": [], "subtask_results": [], "board_tasks": []}
        )
    assert calls == ["researcher"]
    assert out.get("needs_clarification") is True
    assert out["clarification"]["questions"] == ["What topic?"]


@pytest.mark.asyncio
async def test_assemble_clarification_short_circuit():
    from pipelines.coordinator_board.coordinator import coordinator_assemble

    state = {
        "run_id": "",
        "needs_clarification": True,
        "clarification": {
            "task_id": "t1",
            "role": "researcher",
            "title": "Research",
            "issues": ["Too vague."],
            "questions": ["What should I focus on?"],
        },
        "subtask_results": [],
        "messages": [HumanMessage(content="research stuff")],
    }
    with patch(
        "pipelines.coordinator_board.coordinator.get_llm",
    ) as get_llm:
        out = await coordinator_assemble(state)
    get_llm.assert_not_called()
    assert "What should I focus on?" in out["final_text"]
    assert "Too vague." in out["final_text"]
    assert out["final_data"].get("needs_clarification") is True


def test_format_clarification_message():
    msg = format_clarification_message(
        {"issues": ["Missing recipient."], "questions": ["Who should receive this?"]}
    )
    assert "Missing recipient." in msg
    assert "Who should receive this?" in msg
    assert "specialist" not in msg.lower()
