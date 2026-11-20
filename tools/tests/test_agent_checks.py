"""Specialist tool calls stay inside the allowlist, the organization, and the approval gate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core.context.drafts.store import DraftStore
from core.context.projects.store import ProjectStore
from core.context.request import current_mission_id
from core.runtime.board.store import BoardStore
from core.runtime.runs.models import RunStatus
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.schema import SpecialistAction
from pipelines.coordinator_board.specialists import _run_specialist
from tools.registry import ApprovalRequired, run_tool


class _Script:
    def __init__(self, actions: list[SpecialistAction]) -> None:
        self._actions = list(actions)

    async def ainvoke(self, _prompt: str) -> SpecialistAction:
        if not self._actions:
            raise RuntimeError("no more actions")
        return self._actions.pop(0)


class _GitHub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def is_connected(self, _user_id: str, _integration_id: str) -> bool:
        return True

    async def run(self, _user_id: str, integration_id: str, action: str, params: dict) -> dict:
        self.calls.append((integration_id, action, dict(params)))
        return {"id": "1", "full_name": "acme/app", "name": "app", "owner": {"login": "acme"}}


class _Gmail:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def is_connected(self, _user_id: str, _integration_id: str) -> bool:
        return True

    async def run(self, _user_id: str, integration_id: str, action: str, params: dict) -> dict:
        self.calls.append((integration_id, action))
        return {
            "id": "sent-1",
            "to": params.get("to"),
            "subject": params.get("subject"),
            "body": params.get("body"),
        }


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    monkeypatch.setenv("COGNILANCE_APPROVAL_GRADES", "irreversible")
    projects = ProjectStore(db)
    runs = RunStore(db)
    board = BoardStore(db)
    drafts = DraftStore(db)
    for store in (projects, runs, board, drafts):
        store.init_db()
    ours = projects.create_project("org-a", "Launch", created_by="ada")
    theirs = projects.create_project("org-b", "Secret program", created_by="bea")
    run = runs.create_run(
        instruction="Update the launch tasks",
        thread_id="thread-a",
        organization_id="org-a",
        user_id="ada",
        run_id="run-a",
    )
    return {
        "projects": projects,
        "runs": runs,
        "board": board,
        "drafts": drafts,
        "run": run,
        "ours": ours,
        "theirs": theirs,
    }


def _tool_steps(runs: RunStore, run_id: str) -> list:
    return [step for step in runs.list_steps(run_id) if step.kind == "tool_call"]


@pytest.mark.asyncio
async def test_other_organization_project_returns_an_error_and_a_run_step(world):
    projects: ProjectStore = world["projects"]
    runs: RunStore = world["runs"]
    token = current_mission_id.set(world["run"].id)
    try:
        out = await run_tool(
            "project_agent",
            "projects.create_task",
            params={
                "project_id": world["theirs"].id,
                "title": "Stolen",
                "organization_id": "org-b",
            },
        )
    finally:
        current_mission_id.reset(token)

    assert out["status"] == "error"
    assert out["data"]["error"] == "Project not found"
    assert [task for task in projects.list_all_tasks() if task.project_id == world["theirs"].id] == []
    steps = _tool_steps(runs, world["run"].id)
    assert steps[-1].data["tool"] == "projects.create_task"
    assert steps[-1].data["outcome"] == "error"


@pytest.mark.asyncio
async def test_graded_project_and_github_tools_pause_before_they_run(world, monkeypatch):
    monkeypatch.setenv("COGNILANCE_APPROVAL_GRADES", "read,reversible_write")
    projects: ProjectStore = world["projects"]
    github = _GitHub()
    entered = {"github": 0}
    from tools.github import tool as github_tool

    real_run = github_tool.run

    async def _count_github(*args, **kwargs):
        entered["github"] += 1
        return await real_run(*args, **kwargs)

    token = current_mission_id.set(world["run"].id)
    try:
        with patch("tools.github.tool.run", _count_github):
            with pytest.raises(ApprovalRequired) as project_gate:
                await run_tool(
                    "project_agent",
                    "projects.create_task",
                    params={"project_id": world["ours"].id, "title": "Ship it"},
                )
            with pytest.raises(ApprovalRequired) as github_gate:
                await run_tool(
                    "engineering_agent",
                    "github.list_commits",
                    params={"owner": "acme", "repo": "app"},
                    integrations=github,
                )
    finally:
        current_mission_id.reset(token)

    assert project_gate.value.tool == "projects.create_task"
    assert github_gate.value.tool == "github.list_commits"
    assert projects.search_tasks("org-a") == []
    assert entered["github"] == 0
    assert github.calls == []


@pytest.mark.asyncio
async def test_gmail_send_stays_waiting_until_the_approved_resume(world):
    runs: RunStore = world["runs"]
    world["board"].create_task(
        run_id=world["run"].id,
        title="Send the note",
        instruction="Send the email now",
        assignee_role="email_agent",
    )
    script = _Script(
        [
            SpecialistAction(
                status="call_tool",
                tool="gmail.send",
                tool_instruction="Send the note to ada@example.com",
            )
        ]
    )
    gmail = _Gmail()
    token = current_mission_id.set(world["run"].id)
    try:
        with patch(
            "pipelines.coordinator_board.specialists.get_structured_llm",
            return_value=script,
        ):
            update = await _run_specialist(
                {"run_id": world["run"].id, "messages": []},
                "email_agent",
            )
        assert update.get("waiting_approval") is True
        assert runs.get_run(world["run"].id).status == RunStatus.WAITING_APPROVAL
        assert gmail.calls == []

        with pytest.raises(ApprovalRequired):
            await run_tool("email_agent", "gmail.send", integrations=gmail)
        assert runs.get_run(world["run"].id).status == RunStatus.WAITING_APPROVAL
        assert gmail.calls == []

        world["drafts"].save_email_draft(
            world["run"].id,
            {"to": "ada@example.com", "subject": "Hello", "body": "The note."},
        )
        sent = await run_tool(
            "email_agent",
            "gmail.send",
            params={"to": "ada@example.com"},
            integrations=gmail,
            skip_approval_check=True,
        )
    finally:
        current_mission_id.reset(token)

    assert sent["status"] == "completed"
    assert gmail.calls == [("gmail", "send_email")]


@pytest.mark.asyncio
async def test_disallowed_tool_appends_a_denied_run_step(world):
    runs: RunStore = world["runs"]
    token = current_mission_id.set(world["run"].id)
    try:
        with pytest.raises(RuntimeError, match="not allowed to use tool projects.create_task"):
            await run_tool(
                "engineering_agent",
                "projects.create_task",
                params={"project_id": world["ours"].id, "title": "Nope"},
            )
    finally:
        current_mission_id.reset(token)

    steps = _tool_steps(runs, world["run"].id)
    assert steps[-1].data == {
        "tool": "projects.create_task",
        "risk": "reversible_write",
        "outcome": "denied",
    }
