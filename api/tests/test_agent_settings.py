"""Per-organization agent enablement stays inside that organization's catalog and roster."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.responses import Response

from agents.coordinator.schema import PlannedTask
from agents.coordinator.schema import Result as CoordinatorPlan
from api.auth.guard import is_public_request
from api.auth.session import COOKIE_NAME, set_user_cookie
from api.routes import health
from core.context.orgs.store import OrgStore
from core.context.request import current_user_id
from core.context.users.accounts import AccountStore
from core.registry.loader import RegistryError, validate_all
from core.runtime.missions.store import MissionStore
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.coordinator import (
    _organization_id,
    _plan_prompt,
    _roster,
    _validate_assignees,
    coordinator_plan,
)


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")

    accounts = AccountStore(db)
    orgs = OrgStore(db)
    missions = MissionStore(db)
    runs = RunStore(db)
    for store in (accounts, orgs, missions, runs):
        store.init_db()

    monkeypatch.setattr("api.deps.org_store", orgs)
    monkeypatch.setattr(health, "org_store", orgs)

    ada = accounts.create(email="ada@example.com", password="password1", display_name="Ada")
    bea = accounts.create(email="bea@example.com", password="password1", display_name="Bea")
    solo = accounts.create(email="solo@example.com", password="password1", display_name="Solo")
    ada_org = orgs.active_for_account(ada.id)
    bea_org = orgs.active_for_account(bea.id)
    solo_org = orgs.active_for_account(solo.id)
    assert ada_org and bea_org and solo_org
    orgs.delete_organization(solo_org)

    app = FastAPI()

    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        from api.auth.session import get_user_id

        user_id = get_user_id(request)
        request.state.user_id = user_id
        if not user_id and not is_public_request(request):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        token = current_user_id.set(user_id) if user_id else None
        try:
            return await call_next(request)
        finally:
            if token is not None:
                current_user_id.reset(token)

    app.include_router(health.router)
    return {
        "db": db,
        "orgs": orgs,
        "missions": missions,
        "runs": runs,
        "ada": ada,
        "bea": bea,
        "solo": solo,
        "ada_org": ada_org,
        "bea_org": bea_org,
        "client": TestClient(app),
    }


def _cookie(user_id: str) -> str:
    response = Response()
    set_user_cookie(response, user_id)
    header = response.headers["set-cookie"]
    return header.split(";", 1)[0].split("=", 1)[1]


def _agent_ids(response) -> set[str]:
    return {row["id"] for row in response.json()["agents"]}


def test_online_list_hides_a_disabled_agent_for_that_organization_only(world):
    orgs: OrgStore = world["orgs"]
    orgs.set_agent_setting(world["ada_org"], "not_a_real_agent", enabled=False)
    orgs.set_agent_setting(world["ada_org"], "email_agent", enabled=False, extra_instruction="Sign off as Ada.")
    assert orgs.disabled_agent_ids(world["ada_org"]) == {"email_agent"}
    assert orgs.disabled_agent_ids(world["bea_org"]) == set()
    assert orgs.extra_instructions(world["ada_org"]) == {"email_agent": "Sign off as Ada."}
    assert orgs.extra_instructions(world["bea_org"]) == {}

    client: TestClient = world["client"]
    anonymous = _agent_ids(client.get("/skills/online"))
    ada = _agent_ids(client.get("/skills/online", cookies={COOKIE_NAME: _cookie(world["ada"].id)}))
    bea = _agent_ids(client.get("/marketplace/agents", cookies={COOKIE_NAME: _cookie(world["bea"].id)}))
    solo = _agent_ids(client.get("/skills/online", cookies={COOKIE_NAME: _cookie(world["solo"].id)}))

    assert "email_agent" not in ada
    assert "email_agent" in bea
    assert "email_agent" in anonymous
    assert "email_agent" in solo
    assert "researcher" in ada


def test_roster_and_assignees_follow_the_runs_organization(world):
    orgs: OrgStore = world["orgs"]
    orgs.set_agent_setting(world["ada_org"], "email_agent", enabled=False)
    orgs.set_agent_setting(world["bea_org"], "researcher", extra_instruction="Cite the source.")

    ada_prompt = _plan_prompt("Draft a note", roles=_roster(world["ada_org"]))
    bea_prompt = _plan_prompt("Draft a note", roles=_roster(world["bea_org"]))
    assert "- email_agent:" not in ada_prompt
    assert "- email_agent:" in bea_prompt
    assert "Cite the source." in bea_prompt
    assert "Cite the source." not in ada_prompt

    plan = CoordinatorPlan(
        tasks=[
            PlannedTask(title="Mail", instruction="Draft it", assignee_role="email_agent"),
            PlannedTask(title="Look", instruction="Find it", assignee_role="researcher"),
        ]
    )
    ada_kept = _validate_assignees(plan, allowed={role.id for role, _extra in _roster(world["ada_org"])})
    bea_kept = _validate_assignees(plan, allowed={role.id for role, _extra in _roster(world["bea_org"])})
    assert [task.assignee_role for task in ada_kept.tasks] == ["researcher"]
    assert [task.assignee_role for task in bea_kept.tasks] == ["email_agent", "researcher"]

    mission = world["missions"].create_mission(
        instruction="Draft a note",
        user_id=world["ada"].id,
        organization_id=world["ada_org"],
    )
    assert _organization_id({"run_id": mission.id}) == world["ada_org"]
    ada_result = asyncio.run(
        coordinator_plan(
            {
                "run_id": mission.id,
                "messages": [],
                "preset_tasks": [
                    {
                        "id": "mail",
                        "title": "Mail",
                        "instruction": "Draft it",
                        "assignee_role": "email_agent",
                    }
                ],
            }
        )
    )
    assert "email_agent" not in {task["assignee_role"] for task in ada_result["board_tasks"]}

    run = world["runs"].create_run(
        instruction="Draft a note",
        thread_id="thread-bea",
        user_id=world["bea"].id,
        organization_id=world["bea_org"],
    )
    assert _organization_id({"run_id": run.id}) == world["bea_org"]
    bea_result = asyncio.run(
        coordinator_plan(
            {
                "run_id": run.id,
                "messages": [],
                "preset_tasks": [
                    {
                        "id": "mail",
                        "title": "Mail",
                        "instruction": "Draft it",
                        "assignee_role": "email_agent",
                    }
                ],
            }
        )
    )
    assert "email_agent" in {task["assignee_role"] for task in bea_result["board_tasks"]}


def test_bad_agent_yaml_still_fails_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from agents import loader

    coordinator_dir = tmp_path / "coordinator"
    broken_dir = tmp_path / "broken"
    coordinator_dir.mkdir()
    broken_dir.mkdir()
    (coordinator_dir / "agent.yaml").write_text(
        "id: coordinator\nname: Coordinator\ninstructions: Plan the work.\n",
        encoding="utf-8",
    )
    (broken_dir / "agent.yaml").write_text(
        "id: broken\nname: Broken\ninstructions: Draft.\ntools:\n  - not_a_real_tool\n",
        encoding="utf-8",
    )
    loader.load_roles.cache_clear()
    monkeypatch.setattr(loader, "AGENTS_DIR", tmp_path)
    try:
        with pytest.raises(RegistryError, match="unknown tools"):
            validate_all(strict=True, log=False)
    finally:
        loader.load_roles.cache_clear()
