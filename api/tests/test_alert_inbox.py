"""A member sees their organization's open alerts and can acknowledge or dismiss them."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.responses import Response

from api import deps
from api.auth.guard import is_public_request
from api.auth.session import COOKIE_NAME, set_user_cookie
from api.routes import alerts
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.projects.store import ProjectStore
from core.context.request import current_user_id
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.accounts import AccountStore
from workers.schedulers.ticker import tick_subscriptions


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")

    accounts = AccountStore(db)
    orgs = OrgStore(db)
    projects = ProjectStore(db)
    convs = ConversationStore(db)
    subs = SubscriptionStore(db)
    for store in (accounts, orgs, projects, convs, subs):
        store.init_db()

    ada = accounts.create(email="ada@example.com", password="password1", display_name="Ada")
    bea = accounts.create(email="bea@example.com", password="password1", display_name="Bea")
    ada_org = orgs.active_for_account(ada.id)
    bea_org = orgs.active_for_account(bea.id)
    assert ada_org and bea_org and ada_org != bea_org

    monkeypatch.setattr(deps, "org_store", orgs)
    monkeypatch.setattr(deps, "project_store", projects)

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

    app.include_router(alerts.router)
    return {
        "client": TestClient(app),
        "db": db,
        "orgs": orgs,
        "projects": projects,
        "ada": ada,
        "bea": bea,
        "ada_org": ada_org,
    }


def _cookie(user_id: str) -> dict[str, str]:
    response = Response()
    set_user_cookie(response, user_id)
    header = response.headers["set-cookie"]
    value = header.split(";", 1)[0].split("=", 1)[1]
    return {COOKIE_NAME: value}


def _message_count(path: str) -> int:
    with sqlite3.connect(path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0])


def _open_task_alert(world):
    projects: ProjectStore = world["projects"]
    project = projects.create_project(world["ada_org"], "Launch", created_by=world["ada"].id)
    task = projects.create_task(
        project.id,
        organization_id=world["ada_org"],
        title="Ship the brief",
        created_by=world["ada"].id,
        priority="high",
        assignee_account_id=world["ada"].id,
    )
    alert = world["orgs"].open_alert(
        world["ada_org"],
        "Work task is past its deadline: Ship the brief",
        kind="task.overdue",
        source_key=f"task:{task.id}:overdue",
        fingerprint="2026-11-01T00:00:00+00:00",
        priority="high",
        assignee_account_id=world["ada"].id,
        suggested_next_step="Ask the project agent for a status note.",
        link={"type": "task", "task_id": task.id, "project_id": project.id},
    )
    assert alert is not None
    return alert


def test_a_member_sees_their_organization_alert_with_its_link(world):
    alert = _open_task_alert(world)
    client: TestClient = world["client"]
    listed = client.get("/alerts", cookies=_cookie(world["ada"].id))
    assert listed.status_code == 200, listed.text
    rows = listed.json()["alerts"]
    assert len(rows) == 1
    assert rows[0]["id"] == alert.id
    assert rows[0]["priority"] == "high"
    assert rows[0]["assignee_account_id"] == world["ada"].id
    assert rows[0]["read"] is False
    assert rows[0]["link"]["type"] == "task"
    assert rows[0]["link"]["task_id"]
    assert rows[0]["suggested_next_step"] == "Ask the project agent for a status note."

    other = client.get("/alerts", cookies=_cookie(world["bea"].id))
    assert other.status_code == 200, other.text
    assert other.json()["alerts"] == []
    hidden = client.post(
        f"/alerts/{alert.id}/acknowledge",
        cookies=_cookie(world["bea"].id),
    )
    assert hidden.status_code == 404


def test_acknowledge_and_dismiss_persist_without_a_chat_message(world):
    alert = _open_task_alert(world)
    client: TestClient = world["client"]
    ada = _cookie(world["ada"].id)
    assert _message_count(world["db"]) == 0

    acknowledged = client.post(f"/alerts/{alert.id}/acknowledge", cookies=ada)
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["read"] is True
    assert acknowledged.json()["suggested_next_step"] == "Ask the project agent for a status note."
    again = client.get("/alerts", cookies=ada)
    assert again.json()["alerts"][0]["read"] is True

    dismissed = client.post(f"/alerts/{alert.id}/dismiss", cookies=ada)
    assert dismissed.status_code == 200, dismissed.text
    inbox = client.get("/alerts", cookies=ada)
    assert inbox.json()["alerts"] == []
    stored = world["orgs"].get_alert(alert.id)
    assert stored is not None
    assert stored.dismissed_at is not None
    assert stored.acknowledged_at is not None
    assert _message_count(world["db"]) == 0


async def test_detection_puts_the_task_link_on_an_overdue_alert(world):
    projects: ProjectStore = world["projects"]
    project = projects.create_project(world["ada_org"], "Launch", created_by=world["ada"].id)
    deadline = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    task = projects.create_task(
        project.id,
        organization_id=world["ada_org"],
        title="Ship the brief",
        created_by=world["ada"].id,
        priority="high",
        deadline=deadline,
        assignee_account_id=world["ada"].id,
    )
    await tick_subscriptions()
    client: TestClient = world["client"]
    listed = client.get("/alerts", cookies=_cookie(world["ada"].id))
    assert listed.status_code == 200, listed.text
    rows = listed.json()["alerts"]
    assert len(rows) == 1
    assert rows[0]["link"] == {
        "type": "task",
        "task_id": task.id,
        "project_id": project.id,
    }
    assert rows[0]["priority"] == "high"
    assert rows[0]["assignee_account_id"] == world["ada"].id
    assert rows[0]["read"] is False
