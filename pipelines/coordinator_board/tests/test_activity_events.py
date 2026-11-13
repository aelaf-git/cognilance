"""The chat trace receives the brief and the tool instruction, not just the tool id."""

from __future__ import annotations

import pytest

from pipelines.coordinator_board.execute import execute_brief
from pipelines.coordinator_board.models import Brief
from tools.registry import ToolOutput, run_tool


@pytest.mark.asyncio
async def test_execute_brief_emits_the_agent_brief(monkeypatch):
    events: list[dict] = []

    def capture(event: str, **data):
        events.append({"event": event, **data})

    async def runner(pack, *, instruction, messages):
        del pack, instruction, messages
        return {"text": "The file is ready.", "data": {}, "tool": "docx.create"}

    monkeypatch.setattr("pipelines.coordinator_board.execute.emit", capture)
    monkeypatch.setattr("pipelines.coordinator_board.specialists._run_task_loop", runner)

    await execute_brief(
        "docx_agent",
        Brief(
            goal="Write a short history of Napoleon",
            constraints=["One page"],
            success_criteria=["A Word file is saved"],
        ),
    )

    assert events[0]["event"] == "agent_start"
    assert events[0]["role"] == "docx_agent"
    assert events[0]["name"] == "Docx Agent"
    assert "Write a short history of Napoleon" in events[0]["brief"]
    assert "One page" in events[0]["brief"]


@pytest.mark.asyncio
async def test_run_tool_emits_the_instruction_and_a_one_line_summary(monkeypatch):
    events: list[dict] = []

    def capture(event: str, **data):
        events.append({"event": event, **data})

    class FakeTool:
        async def run(self, action, *, instruction, params, ctx):
            del action, instruction, params, ctx
            return ToolOutput(text='Created Word file "Napoleon" (doc_abc).\nStyle: Georgia headings.')

    monkeypatch.setattr("pipelines.shared.streaming.emit", capture)
    monkeypatch.setattr("tools.registry._tool_module", lambda base: FakeTool())

    await run_tool(
        "docx_agent",
        "docx.create",
        instruction='{"title":"Napoleon"}',
        integrations=object(),
        skip_approval_check=True,
    )

    start = next(item for item in events if item["event"] == "tool_start")
    done = next(item for item in events if item["event"] == "tool_done")
    assert start["tool"] == "docx.create"
    assert start["assignee"] == "docx_agent"
    assert start["instruction"] == '{"title":"Napoleon"}'
    assert done["summary"] == 'Created Word file "Napoleon" (doc_abc).'
    assert "Georgia" not in done["summary"]
