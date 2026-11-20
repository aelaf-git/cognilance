"""project_agent lists one organization's overdue work and updates tasks through the tool."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from agents.loader import get_role, load_roles
from core.context.projects.store import ProjectStore
from core.context.request import current_mission_id
from core.runtime.board.store import BoardStore
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.schema import SpecialistAction, VerificationResult
from pipelines.coordinator_board.specialists import _run_specialist
from tools.projects import tool
from tools.registry import ToolContext, load_manifests, validate_tool_ids


class _Script:
    def __init__(self, actions: list[SpecialistAction]) -> None:
        self._actions = list(actions)

    async def ainvoke(self, _prompt: str) -> SpecialistAction:
        if not self._actions:
            raise RuntimeError("no more actions")
        return self._actions.pop(0)


def _ctx(tool_id: str) -> ToolContext:
    return ToolContext(
        role_id="project_agent",
        user_id="ada",
        client=None,
        tool_id=tool_id,
        risk="read",
    )


@pytest.fixture
def world(tmp_path, monkeypatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    projects = ProjectStore(db)
    runs = RunStore(db)
    board = BoardStore(db)
    for store in (projects, runs, board):
        store.init_db()
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    ours = projects.create_project("org-a", "Launch", created_by="ada")
    theirs = projects.create_project("org-b", "Secret program", created_by="bea")
    overdue = projects.create_task(
        ours.id,
        organization_id="org-a",
        title="File the brief",
        created_by="ada",
        deadline=past,
        status="open",
    )
    projects.create_task(
        ours.id,
        organization_id="org-a",
        title="Later note",
        created_by="ada",
        deadline=future,
        status="open",
    )
    projects.create_task(
        ours.id,
        organization_id="org-a",
        title="Already finished",
        created_by="ada",
        deadline=past,
        status="done",
    )
    hidden = projects.create_task(
        theirs.id,
        organization_id="org-b",
        title="Other org secret",
        created_by="bea",
        deadline=past,
        status="open",
    )
    run = runs.create_run(
        instruction="List overdue work",
        thread_id="thread-a",
        organization_id="org-a",
        user_id="ada",
        run_id="run-a",
    )
    return {
        "projects": projects,
        "board": board,
        "run": run,
        "overdue": overdue,
        "hidden": hidden,
    }


@pytest.mark.asyncio
async def test_board_task_lists_overdue_work_for_the_run_organization(world):
    world["board"].create_task(
        run_id=world["run"].id,
        title="Overdue",
        instruction="List overdue work tasks",
        assignee_role="project_agent",
    )
    script = _Script(
        [
            SpecialistAction(
                status="call_tool",
                tool="projects.search_tasks",
                tool_instruction='{"overdue": true}',
            ),
            SpecialistAction(status="done", answer=""),
        ]
    )
    token = current_mission_id.set(world["run"].id)
    try:
        with (
            patch(
                "pipelines.coordinator_board.specialists.get_structured_llm",
                return_value=script,
            ),
            patch(
                "pipelines.coordinator_board.specialists.verify_task_output",
                new=AsyncMock(return_value=VerificationResult(passed=True, reasoning="ok")),
            ),
        ):
            update = await _run_specialist({"run_id": world["run"].id, "messages": []}, "project_agent")
    finally:
        current_mission_id.reset(token)

    text = update["subtask_results"][0]["text"]
    assert "File the brief" in text
    assert "Other org secret" not in text
    assert "Secret program" not in text
    assert "Later note" not in text
    assert "Already finished" not in text
    titles = [item["title"] for item in update["subtask_results"][0]["data"]["result"]["overdue"]]
    assert titles == ["File the brief"]


@pytest.mark.asyncio
async def test_update_records_the_agent_and_hides_the_other_organization(world):
    token = current_mission_id.set(world["run"].id)
    try:
        updated = await tool.run(
            "update_task",
            instruction="",
            params={"task_id": world["overdue"].id, "status": "in_progress"},
            ctx=_ctx("projects.update_task"),
        )
        denied = await tool.run(
            "update_task",
            instruction="",
            params={"task_id": world["hidden"].id, "status": "done", "organization_id": "org-b"},
            ctx=_ctx("projects.update_task"),
        )
    finally:
        current_mission_id.reset(token)

    assert updated.data["task"]["status"] == "in_progress"
    activity = world["projects"].list_activity(world["overdue"].id, organization_id="org-a")
    assert activity[-1].action == "updated"
    assert activity[-1].actor_id == "project_agent"
    assert denied.data["error"] == "not found"
    hidden = world["projects"].get_task(world["hidden"].id, organization_id="org-b")
    assert hidden is not None
    assert hidden.status == "open"
    hidden_activity = world["projects"].list_activity(world["hidden"].id, organization_id="org-b")
    assert [row.action for row in hidden_activity] == ["created"]


def test_project_tool_ids_are_registered():
    load_roles.cache_clear()
    load_manifests.cache_clear()
    assert get_role("project_agent") is not None
    assert validate_tool_ids(
        [
            "projects.search",
            "projects.search_tasks",
            "projects.create_task",
            "projects.update_task",
        ]
    ) == []
