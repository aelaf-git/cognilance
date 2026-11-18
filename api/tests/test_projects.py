"""Members manage organization projects without touching the run board."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from api.auth.guard import is_public_request
from api.auth.session import get_user_id
from api.routes import auth, projects
from core.context.orgs.store import OrgStore
from core.context.projects.store import ProjectStore
from core.context.request import current_user_id, current_user_timezone
from core.context.users.accounts import AccountStore
from core.context.users.store import UserPreferencesStore
from core.context.users.timezone import activate_user_timezone, client_timezone_from_request
from core.runtime.board.store import BoardStore


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")

    accounts = AccountStore(db)
    orgs = OrgStore(db)
    prefs = UserPreferencesStore(db)
    project_store = ProjectStore(db)
    board = BoardStore(db)
    for store in (accounts, orgs, prefs, project_store, board):
        store.init_db()

    monkeypatch.setattr(auth, "account_store", accounts)
    monkeypatch.setattr("api.deps.account_store", accounts)
    monkeypatch.setattr("api.deps.org_store", orgs)
    monkeypatch.setattr("api.deps.project_store", project_store)
    monkeypatch.setattr("core.context.users.timezone._store", prefs)

    app = FastAPI()

    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        user_id = get_user_id(request)
        request.state.user_id = user_id
        if not user_id and not is_public_request(request):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        user_token = None
        tz_token = None
        if user_id:
            user_token = current_user_id.set(user_id)
            tz_token = activate_user_timezone(
                user_id, from_client=client_timezone_from_request(request)
            )
        try:
            return await call_next(request)
        finally:
            if tz_token is not None:
                current_user_timezone.reset(tz_token)
            if user_token is not None:
                current_user_id.reset(user_token)

    app.include_router(auth.router)
    app.include_router(projects.router)

    with TestClient(app) as client:
        yield {"client": client, "db": db, "accounts": accounts}


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password1", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _board_count(db: str) -> int:
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT COUNT(*) FROM board_tasks").fetchone()
    return int(row[0])


def test_member_creates_assigns_comments_and_reads_activity(world):
    client = world["client"]
    member = _register(client, "member@example.com")
    created = client.post("/projects", json={"title": "Alpha"})
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]

    task = client.post(
        f"/projects/{project_id}/tasks",
        json={
            "title": "Ship the login fix",
            "assignee_account_id": member["id"],
            "priority": "high",
            "deadline": "2026-11-20",
        },
    )
    assert task.status_code == 200, task.text
    body = task.json()
    assert body["assignee_account_id"] == member["id"]
    assert body["assignee_agent_id"] is None
    assert body["status"] == "open"
    task_id = body["id"]

    comment = client.post(
        f"/projects/{project_id}/tasks/{task_id}/comments",
        json={"body": "Started on the timeout."},
    )
    assert comment.status_code == 200, comment.text

    activity = client.get(f"/projects/{project_id}/tasks/{task_id}/activity")
    assert activity.status_code == 200, activity.text
    actions = [row["action"] for row in activity.json()["activity"]]
    assert actions == ["created", "commented"]
    assert _board_count(world["db"]) == 0


def test_task_can_be_assigned_to_an_agent(world):
    client = world["client"]
    _register(client, "member@example.com")
    project_id = client.post("/projects", json={"title": "Alpha"}).json()["id"]
    task_id = client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Weekly summary"},
    ).json()["id"]

    updated = client.patch(
        f"/projects/{project_id}/tasks/{task_id}",
        json={"assignee_agent_id": "report_writer"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["assignee_agent_id"] == "report_writer"
    assert updated.json()["assignee_account_id"] is None

    unknown = client.patch(
        f"/projects/{project_id}/tasks/{task_id}",
        json={"assignee_agent_id": "not_an_agent"},
    )
    assert unknown.status_code == 400


def test_outsider_cannot_see_another_organizations_project(world):
    client = world["client"]
    _register(client, "owner@example.com")
    project_id = client.post("/projects", json={"title": "Alpha"}).json()["id"]

    _register(client, "outsider@example.com")
    assert client.get(f"/projects/{project_id}").status_code == 404
    assert client.get("/projects").json()["projects"] == []
    assert client.get(f"/projects/{project_id}/tasks").status_code == 404
