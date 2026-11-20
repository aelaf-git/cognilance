"""Team tools stay inside the run's organization and record the call on the run."""

from __future__ import annotations

import pytest

from agents.loader import RolePack
from core.context.orgs.store import OrgStore
from core.context.projects.store import ProjectStore
from core.context.request import current_mission_id
from core.runtime.runs.store import RunStore
from tools.registry import ApprovalRequired, load_manifests, run_tool, tool_risk


def _role(*tools: str) -> RolePack:
    return RolePack(id="tester", name="Tester", instructions="", tools=tools)


@pytest.fixture
def world(tmp_path, monkeypatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    monkeypatch.setenv("COGNILANCE_APPROVAL_GRADES", "irreversible")
    load_manifests.cache_clear()
    projects = ProjectStore(db)
    runs = RunStore(db)
    orgs = OrgStore(db)
    for store in (projects, runs, orgs):
        store.init_db()
    run = runs.create_run(
        instruction="Update the launch tasks",
        thread_id="thread-a",
        organization_id="org-a",
        user_id="ada",
        run_id="run-a",
    )
    project = projects.create_project("org-a", "Launch", created_by="ada")
    return {"projects": projects, "runs": runs, "orgs": orgs, "run": run, "project": project}


@pytest.mark.asyncio
async def test_specialist_without_tasks_update_cannot_call_it():
    with pytest.raises(RuntimeError, match="not allowed to use tool tasks.update"):
        await run_tool("engineering_agent", "tasks.update", params={"task_id": "missing"})


@pytest.mark.asyncio
async def test_create_without_a_title_is_invalid_and_writes_nothing(world):
    token = current_mission_id.set(world["run"].id)
    try:
        out = await run_tool(
            _role("tasks.create"),
            "tasks.create",
            params={"project_id": world["project"].id},
        )
    finally:
        current_mission_id.reset(token)
    assert out["status"] == "error"
    assert out["data"]["error"] == "invalid_params"
    assert "title" in out["data"]["fields"]
    assert world["projects"].search_tasks("org-a") == []


@pytest.mark.asyncio
async def test_allowed_search_records_tool_risk_and_outcome(world):
    projects: ProjectStore = world["projects"]
    projects.create_task(
        world["project"].id,
        organization_id="org-a",
        title="Ship the login fix",
        created_by="ada",
    )
    token = current_mission_id.set(world["run"].id)
    try:
        out = await run_tool(_role("tasks.search"), "tasks.search", params={"query": "login"})
    finally:
        current_mission_id.reset(token)
    assert out["status"] == "completed"
    assert out["risk"] == "read"
    assert "Ship the login fix" in out["text"]
    steps = [step for step in world["runs"].list_steps(world["run"].id) if step.kind == "tool_call"]
    assert steps[-1].data["tool"] == "tasks.search"
    assert steps[-1].data["risk"] == "read"
    assert steps[-1].data["outcome"] == "completed"


@pytest.mark.asyncio
async def test_update_does_not_touch_another_organizations_task(world):
    projects: ProjectStore = world["projects"]
    other = projects.create_project("org-b", "Secret", created_by="bea")
    hidden = projects.create_task(
        other.id,
        organization_id="org-b",
        title="Hidden",
        created_by="bea",
    )
    token = current_mission_id.set(world["run"].id)
    try:
        out = await run_tool(
            _role("tasks.update"),
            "tasks.update",
            params={"task_id": hidden.id, "title": "Stolen"},
        )
    finally:
        current_mission_id.reset(token)
    assert out["status"] == "error"
    assert projects.get_task(hidden.id, organization_id="org-b").title == "Hidden"


@pytest.mark.asyncio
async def test_alert_requires_a_summary_and_stays_in_the_organization(world):
    orgs: OrgStore = world["orgs"]
    token = current_mission_id.set(world["run"].id)
    try:
        missing = await run_tool(_role("alerts.create"), "alerts.create", params={})
        saved = await run_tool(
            _role("alerts.create"),
            "alerts.create",
            params={"summary": "Build failed", "severity": "warning", "kind": "build"},
        )
    finally:
        current_mission_id.reset(token)
    assert missing["status"] == "error"
    assert missing["data"]["error"] == "invalid_params"
    assert saved["status"] == "completed"
    rows = orgs.list_alerts("org-a")
    assert len(rows) == 1
    assert rows[0].organization_id == "org-a"
    assert rows[0].summary == "Build failed"
    assert rows[0].severity == "warning"
    assert orgs.list_alerts("org-b") == []


@pytest.mark.asyncio
async def test_approval_request_pauses_only_with_a_reason(world):
    assert tool_risk("approval.request") == "read"
    assert tool_risk("tasks.create") == "reversible_write"
    token = current_mission_id.set(world["run"].id)
    try:
        missing = await run_tool(_role("approval.request"), "approval.request", params={})
        with pytest.raises(ApprovalRequired) as caught:
            await run_tool(
                _role("approval.request"),
                "approval.request",
                params={"reason": "Send the note"},
            )
    finally:
        current_mission_id.reset(token)
    assert missing["status"] == "error"
    assert missing["data"]["error"] == "invalid_params"
    assert "reason" in missing["data"]["fields"]
    assert caught.value.tool == "approval.request"
    assert caught.value.risk == "read"
    steps = [step for step in world["runs"].list_steps(world["run"].id) if step.kind == "tool_call"]
    assert steps[-1].data == {
        "tool": "approval.request",
        "risk": "read",
        "outcome": "paused",
    }
