"""Unit tests for the specialist observe→act loop and LLM assemble."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from pipelines.coordinator_board.schema import SpecialistAction
from pipelines.coordinator_board.specialists import _pick_tool, _run_task_loop, _run_specialist
from tools.registry import ApprovalRequired


class _FakeStructured:
    def __init__(self, actions: list[SpecialistAction]):
        self._actions = list(actions)

    async def ainvoke(self, _prompt: str):
        if not self._actions:
            raise RuntimeError("no more actions")
        return self._actions.pop(0)


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
async def test_loop_done_without_tools():
    pack = _pack()
    actions = [
        SpecialistAction(status="done", answer="Hello there.", reasoning="greeting"),
    ]
    with (
        patch(
            "pipelines.coordinator_board.specialists.get_structured_llm",
            return_value=_FakeStructured(actions),
        ),
        patch(
            "pipelines.coordinator_board.specialists.run_role_tool",
            new_callable=AsyncMock,
        ) as run_tool,
    ):
        out = await _run_task_loop(
            pack,
            instruction="Reply conversationally to: Hey",
            messages=[HumanMessage(content="Hey")],
        )
    assert out["text"] == "Hello there."
    run_tool.assert_not_called()


@pytest.mark.asyncio
async def test_loop_tool_then_done():
    pack = _pack()
    actions = [
        SpecialistAction(
            status="call_tool",
            tool="web.search",
            tool_instruction="capital of France",
            reasoning="need facts",
        ),
        SpecialistAction(status="done", answer="Paris is the capital of France."),
    ]
    with (
        patch(
            "pipelines.coordinator_board.specialists.get_structured_llm",
            return_value=_FakeStructured(actions),
        ),
        patch(
            "pipelines.coordinator_board.specialists.run_role_tool",
            new_callable=AsyncMock,
            return_value={
                "text": "Paris ... capital",
                "data": {"sources": ["https://example.com"]},
                "risk": "read",
            },
        ) as run_tool,
    ):
        out = await _run_task_loop(
            pack,
            instruction="What is the capital of France? Research if needed.",
            messages=[HumanMessage(content="capital of France?")],
        )
    assert out["text"] == "Paris is the capital of France."
    assert out["data"].get("sources") == ["https://example.com"]
    run_tool.assert_awaited_once()
    assert run_tool.await_args.kwargs["instruction"] == "capital of France"


@pytest.mark.asyncio
async def test_loop_approval_required_bubbles():
    pack = _pack(id="email_agent", tools=("gmail.draft", "gmail.send", "thinking"))
    actions = [
        SpecialistAction(
            status="call_tool",
            tool="gmail.send",
            tool_instruction="send the draft",
        ),
    ]
    with (
        patch(
            "pipelines.coordinator_board.specialists.get_structured_llm",
            return_value=_FakeStructured(actions),
        ),
        patch(
            "pipelines.coordinator_board.specialists.run_role_tool",
            new_callable=AsyncMock,
            side_effect=ApprovalRequired("gmail.send", "send", {}, "irreversible"),
        ),
    ):
        with pytest.raises(ApprovalRequired):
            await _run_task_loop(
                pack,
                instruction="Send the email now",
                messages=[],
            )


@pytest.mark.asyncio
async def test_run_specialist_sets_waiting_approval():
    pack = _pack(id="email_agent", name="Email", tools=("gmail.send", "thinking"))
    state = {
        "run_id": "",
        "messages": [HumanMessage(content="send it")],
        "board_tasks": [
            {
                "id": "t1",
                "title": "Send",
                "instruction": "Send the email now",
                "assignee_role": "email_agent",
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
            side_effect=ApprovalRequired("gmail.send", "send", {"x": 1}, "irreversible"),
        ),
    ):
        update = await _run_specialist(state, "email_agent")
    assert update.get("waiting_approval") is True
    assert update["pending_approval"]["tool"] == "gmail.send"
    assert update["pending_approval"]["task_id"] == "t1"


@pytest.mark.asyncio
async def test_assemble_uses_llm_with_join_fallback():
    from pipelines.coordinator_board.coordinator import coordinator_assemble

    state = {
        "run_id": "",
        "waiting_approval": False,
        "messages": [HumanMessage(content="summarize")],
        "subtask_results": [
            {
                "subtask_id": "a",
                "text": "Fact one.",
                "data": {},
                "assignee": "researcher",
                "status": "completed",
            }
        ],
    }
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(
        return_value=SimpleNamespace(content="Synthesized answer for the user.")
    )
    with (
        patch(
            "pipelines.coordinator_board.coordinator.get_llm",
            return_value=fake_llm,
        ),
        patch(
            "pipelines.coordinator_board.coordinator.coordinator",
            return_value=SimpleNamespace(
                prompts={"assemble": "Combine results cleanly."},
                instructions="coord",
            ),
        ),
    ):
        out = await coordinator_assemble(state)
    assert out["final_text"] == "Synthesized answer for the user."


@pytest.mark.asyncio
async def test_assemble_falls_back_to_join_on_llm_error():
    from pipelines.coordinator_board.coordinator import coordinator_assemble

    state = {
        "run_id": "",
        "waiting_approval": False,
        "messages": [HumanMessage(content="summarize")],
        "subtask_results": [
            {
                "subtask_id": "a",
                "text": "Alpha",
                "data": {},
                "assignee": "researcher",
                "status": "completed",
            },
            {
                "subtask_id": "b",
                "text": "Beta",
                "data": {},
                "assignee": "report_writer",
                "status": "completed",
            },
        ],
    }
    with patch(
        "pipelines.coordinator_board.coordinator.get_llm",
        side_effect=RuntimeError("no key"),
    ):
        out = await coordinator_assemble(state)
    assert out["final_text"] == "Alpha\n\nBeta"


def test_pick_tool_regressions_still_importable():
    tools = ("web.search", "link_validate.check", "thinking")
    assert _pick_tool("researcher", "Hey", tools) == "thinking"
    assert _pick_tool("researcher", "search the latest news", tools) == "web.search"
