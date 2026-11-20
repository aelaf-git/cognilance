"""Audit rows record approvals, invites, and disconnects, and stay unchanged by task edits."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from starlette.responses import Response

from api import deps
from api.auth.guard import is_public_request
from api.auth.session import COOKIE_NAME, set_user_cookie
from api.routes import audit, integrations, organizations, projects, runs
from core.broker.oauth import OAuthService
from core.broker.store import IntegrationStore
from core.context.orgs.store import OrgStore
from core.context.projects.store import ProjectStore
from core.context.request import current_user_id
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.accounts import AccountStore
from core.runtime.missions.models import MissionStatus
from core.runtime.missions.store import MissionStore
from core.runtime.runs.models import RunStatus
from core.runtime.runs.store import RunStore


class _Graph:
    async def aget_state(self, config):
        return SimpleNamespace(next=(), interrupts=(), values={})

    async def astream(self, graph_input, config, stream_mode=None):
        yield "values", {"messages": [AIMessage(content="continued")]}


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")
    accounts = AccountStore(db)
    orgs = OrgStore(db)
    projects_store = ProjectStore(db)
    missions = MissionStore(db)
    run_store = RunStore(db)
    integrations_store = IntegrationStore(db)
    subscriptions = SubscriptionStore(db)
    for store in (
        accounts,
        orgs,
        projects_store,
        missions,
        run_store,
        integrations_store,
        subscriptions,
    ):
        store.init_db()
    ada = accounts.create(email="ada@example.com", password="password1", display_name="Ada")
    bea = accounts.create(email="bea@example.com", password="password1", display_name="Bea")
    cam = accounts.create(email="cam@example.com", password="password1", display_name="Cam")
    ada_org = orgs.active_for_account(ada.id)
    bea_org = orgs.active_for_account(bea.id)
    cam_org = orgs.active_for_account(cam.id)
    assert ada_org and bea_org and cam_org
    orgs.add_membership(ada_org, cam.id, "member")
    orgs.delete_organization(cam_org)

    monkeypatch.setattr(deps, "account_store", accounts)
    monkeypatch.setattr(deps, "org_store", orgs)
    monkeypatch.setattr(deps, "project_store", projects_store)
    monkeypatch.setattr(deps, "oauth_service", OAuthService(integrations_store))
    monkeypatch.setattr(runs, "run_store", run_store)
    monkeypatch.setattr(runs, "mission_store", missions)

    async def ensure_graph(*, with_checkpointer: bool = True):
        return _Graph()

    monkeypatch.setattr("core.runtime.runner.ensure_graph", ensure_graph)

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

    app.include_router(audit.router)
    app.include_router(organizations.router)
    app.include_router(integrations.router)
    app.include_router(runs.router)
    app.include_router(projects.router)
    return {
        "client": TestClient(app),
        "orgs": orgs,
        "projects": projects_store,
        "missions": missions,
        "runs": run_store,
        "ada": ada,
        "bea": bea,
        "cam": cam,
        "ada_org": ada_org,
        "bea_org": bea_org,
    }


def _cookie(user_id: str) -> dict[str, str]:
    response = Response()
    set_user_cookie(response, user_id)
    header = response.headers["set-cookie"]
    value = header.split(";", 1)[0].split("=", 1)[1]
    return {COOKIE_NAME: value}


def test_approval_invite_and_disconnect_are_readable_and_task_edits_leave_them(world):
    client: TestClient = world["client"]
    orgs: OrgStore = world["orgs"]
    ada = _cookie(world["ada"].id)
    bea = _cookie(world["bea"].id)
    waiting = world["missions"].create_mission(
        instruction="Send the note",
        thread_id="thread-waiting",
        user_id=world["ada"].id,
        organization_id=world["ada_org"],
    )
    world["missions"].update_status(waiting.id, MissionStatus.WAITING_APPROVAL)
    world["runs"].create_run(
        instruction="Send the note",
        thread_id="thread-waiting",
        conversation_id="thread-waiting",
        user_id=world["ada"].id,
        organization_id=world["ada_org"],
        mission_id=waiting.id,
        run_id=waiting.id,
    )
    world["runs"].update_status(waiting.id, RunStatus.WAITING_APPROVAL)

    approved = client.post(
        f"/runs/{waiting.id}/resume",
        json={"approved": True},
        cookies=ada,
    )
    assert approved.status_code == 200, approved.text

    invited = client.post(
        f"/organizations/{world['ada_org']}/invitations",
        json={"email": "bea@example.com"},
        cookies=ada,
    )
    assert invited.status_code == 200, invited.text
    accepted = client.post(f"/invitations/{invited.json()['token']}/accept", cookies=bea)
    assert accepted.status_code == 200, accepted.text

    disconnected = client.post("/integrations/github/disconnect", cookies=ada)
    assert disconnected.status_code == 200, disconnected.text

    listed = client.get("/audit", cookies=ada)
    assert listed.status_code == 200, listed.text
    events = listed.json()["events"]
    actions = [event["action"] for event in events]
    assert actions.count("approval.approved") == 1
    assert actions.count("membership.accepted") == 1
    assert actions.count("integration.disconnected") == 1
    approval = next(event for event in events if event["action"] == "approval.approved")
    invite = next(event for event in events if event["action"] == "membership.accepted")
    disconnect = next(event for event in events if event["action"] == "integration.disconnected")
    assert approval["target_id"] == waiting.id
    assert approval["actor_account_id"] == world["ada"].id
    assert invite["target_id"] == invited.json()["id"]
    assert invite["actor_account_id"] == world["bea"].id
    assert disconnect["target_id"] == "github"
    assert disconnect["organization_id"] == world["ada_org"]

    filtered = client.get("/audit", params={"action": "approval.approved"}, cookies=ada)
    assert [event["action"] for event in filtered.json()["events"]] == ["approval.approved"]
    assert client.get("/audit", cookies=bea).json()["events"] == []

    denied = client.get("/audit", cookies=_cookie(world["cam"].id))
    assert denied.status_code == 403

    project = world["projects"].create_project(
        world["ada_org"], "Launch", created_by=world["ada"].id
    )
    task = world["projects"].create_task(
        project.id,
        organization_id=world["ada_org"],
        title="Write the brief",
        created_by=world["ada"].id,
    )
    before = client.get("/audit", cookies=ada).json()["events"]
    edited = client.patch(
        f"/projects/{project.id}/tasks/{task.id}",
        json={"title": "Write the longer brief"},
        cookies=ada,
    )
    assert edited.status_code == 200, edited.text
    after = client.get("/audit", cookies=ada).json()["events"]
    assert after == before
    assert orgs.list_audit(world["bea_org"]) == []
