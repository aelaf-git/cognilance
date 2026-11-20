"""Weekly report reads one organization's tasks and cites recommendations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from agents.loader import get_role
from core.context.conversations.store import ConversationStore
from core.context.projects.store import ProjectStore
from core.context.request import current_mission_id, current_user_id
from core.runtime.missions.store import MissionStore
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.coordinator import coordinator_assemble, coordinator_plan
from pipelines.coordinator_board.schema import SpecialistAction, VerificationResult
from pipelines.coordinator_board.specialists import specialists_fanout
from pipelines.coordinator_board.verify import verify_task_output
from pipelines.weekly_report.graph import preset


class _Script:
    def __init__(self, actions: list[SpecialistAction]) -> None:
        self._actions = list(actions)

    async def ainvoke(self, _prompt: str) -> SpecialistAction:
        if not self._actions:
            raise RuntimeError("no more actions")
        return self._actions.pop(0)


class _GitHub:
    def __init__(self, *, connected: bool) -> None:
        self.connected = connected

    def is_connected(self, _user_id: str, integration_id: str) -> bool:
        return self.connected and integration_id == "github"


def test_preset_skips_github_when_disconnected():
    with patch("core.broker.client.IntegrationClient", return_value=_GitHub(connected=False)):
        roles = [task["assignee_role"] for task in preset("weekly")]
    assert roles == ["project_agent", "report_writer"]


def test_preset_includes_github_when_connected():
    token = current_user_id.set("ada")
    try:
        with patch("core.broker.client.IntegrationClient", return_value=_GitHub(connected=True)):
            tasks = preset("weekly")
    finally:
        current_user_id.reset(token)
    assert [task["assignee_role"] for task in tasks] == [
        "project_agent",
        "engineering_agent",
        "report_writer",
    ]
    assert len(tasks[-1]["depends_on"]) == 2


@pytest.mark.asyncio
async def test_weekly_report_includes_the_organization_task_and_can_be_reopened(tmp_path, monkeypatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    projects = ProjectStore(db)
    runs = RunStore(db)
    conversations = ConversationStore(db)
    for store in (projects, runs, conversations, MissionStore(db)):
        store.init_db()
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    ours = projects.create_project("org-a", "Launch", created_by="ada")
    theirs = projects.create_project("org-b", "Secret program", created_by="bea")
    projects.create_task(
        ours.id,
        organization_id="org-a",
        title="File the brief",
        created_by="ada",
        deadline=past,
        status="open",
    )
    projects.create_task(
        theirs.id,
        organization_id="org-b",
        title="Other org secret",
        created_by="bea",
        deadline=past,
        status="open",
    )
    run = runs.create_run(
        instruction="Write the weekly report",
        thread_id="thread-a",
        organization_id="org-a",
        user_id="ada",
        run_id="run-a",
    )
    script = _Script(
        [
            SpecialistAction(status="call_tool", tool="projects.search_tasks", tool_instruction="{}"),
            SpecialistAction(status="done", answer=""),
            SpecialistAction(
                status="done",
                answer="Completed work\n\nDelayed work\n\nRecommendations\n- No recommendations",
            ),
        ]
    )
    token = current_mission_id.set(run.id)
    try:
        with (
            patch("core.broker.client.IntegrationClient", return_value=_GitHub(connected=False)),
            patch(
                "pipelines.coordinator_board.specialists.get_structured_llm",
                return_value=script,
            ),
            patch(
                "pipelines.coordinator_board.specialists.verify_task_output",
                new=AsyncMock(return_value=VerificationResult(passed=True, reasoning="ok")),
            ),
        ):
            planned = await coordinator_plan(
                {
                    "run_id": run.id,
                    "pipeline": "weekly_report",
                    "messages": [HumanMessage(content="Write the weekly report")],
                    "preset_tasks": preset("Write the weekly report"),
                }
            )
            ran = await specialists_fanout(
                {
                    **planned,
                    "run_id": run.id,
                    "messages": [HumanMessage(content="Write the weekly report")],
                }
            )
        with patch(
            "pipelines.coordinator_board.coordinator.get_llm",
            side_effect=RuntimeError("no model"),
        ):
            assembled = await coordinator_assemble({**planned, **ran, "run_id": run.id})
    finally:
        current_mission_id.reset(token)

    report = assembled["final_text"]
    assert "File the brief" in report
    assert "Other org secret" not in report
    conversation = conversations.create_conversation(title="Weekly", organization_id="org-a", user_id="ada")
    conversations.append_message(conversation.id, role="assistant", content=report)
    reopened = ConversationStore(db).list_messages(conversation.id)
    assert any(item.role == "assistant" and "File the brief" in item.content for item in reopened)


@pytest.mark.asyncio
async def test_uncited_recommendation_fails_without_the_model():
    pack = get_role("report_writer")
    assert pack is not None
    with patch("pipelines.coordinator_board.verify.get_structured_llm") as get_llm:
        result = await verify_task_output(
            pack,
            instruction=(
                "Sections: Recommendations. Every recommendation quotes a work-task id "
                "or a GitHub URL."
            ),
            text="Recommendations\n- Ship the login fix\n",
            data={},
        )
    assert result.passed is False
    assert result.reasoning == "uncited_recommendation"
    get_llm.assert_not_called()


@pytest.mark.asyncio
async def test_no_recommendations_is_not_a_citation_failure():
    pack = get_role("report_writer")
    assert pack is not None
    fake = MagicMock()
    fake.ainvoke = AsyncMock(return_value=VerificationResult(passed=True, reasoning="ok"))
    with (
        patch("pipelines.coordinator_board.verify.get_structured_llm", return_value=fake),
        patch(
            "pipelines.coordinator_board.verify.coordinator",
            return_value=MagicMock(prompts={"verify": "Verify."}),
        ),
    ):
        result = await verify_task_output(
            pack,
            instruction="Sections: Recommendations.",
            text="Recommendations\n- No recommendations\n",
            data={},
        )
    assert result.passed is True
    fake.ainvoke.assert_awaited()
