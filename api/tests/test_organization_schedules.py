"""An admin can schedule a weekly report without a chat phrase."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.responses import Response

from api import deps
from api.auth.guard import is_public_request
from api.auth.session import COOKIE_NAME, set_user_cookie
from api.routes import conversations, organizations, sessions
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.request import current_user_id
from core.context.subscriptions.models import SubscriptionStatus
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.accounts import AccountStore
from core.context.users.store import UserPreferencesStore
from core.runtime.missions.store import MissionStore


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")

    accounts = AccountStore(db)
    orgs = OrgStore(db)
    prefs = UserPreferencesStore(db)
    missions = MissionStore(db)
    subs = SubscriptionStore(db)
    convs = ConversationStore(db)
    for store in (accounts, orgs, prefs, missions, subs, convs):
        store.init_db()

    ada = accounts.create(email="ada@example.com", password="password1", display_name="Ada")
    cam = accounts.create(email="cam@example.com", password="password1", display_name="Cam")
    ada_org = orgs.active_for_account(ada.id)
    cam_org = orgs.active_for_account(cam.id)
    assert ada_org and cam_org
    orgs.add_membership(ada_org, cam.id, "member")
    orgs.delete_organization(cam_org)
    prefs.set_timezone(ada.id, "Africa/Nairobi")

    monkeypatch.setattr(deps, "org_store", orgs)
    monkeypatch.setattr(deps, "sub_store", subs)
    monkeypatch.setattr(deps, "mission_store", missions)
    monkeypatch.setattr(deps, "conv_store", convs)
    monkeypatch.setattr(sessions, "mission_store", missions)
    monkeypatch.setattr(sessions, "sub_store", subs)
    monkeypatch.setattr(conversations, "mission_store", missions)
    monkeypatch.setattr(conversations, "sub_store", subs)
    monkeypatch.setattr(conversations, "conv_store", convs)
    monkeypatch.setattr("core.context.users.timezone._store", prefs)

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

    app.include_router(organizations.router)
    app.include_router(sessions.router)
    app.include_router(conversations.router)
    return {
        "client": TestClient(app),
        "orgs": orgs,
        "subs": subs,
        "convs": convs,
        "ada": ada,
        "cam": cam,
        "ada_org": ada_org,
    }


def _cookie(user_id: str) -> dict[str, str]:
    response = Response()
    set_user_cookie(response, user_id)
    header = response.headers["set-cookie"]
    value = header.split(";", 1)[0].split("=", 1)[1]
    return {COOKIE_NAME: value}


def test_admin_schedule_stores_config_and_falls_back_to_the_creator_timezone(world):
    client: TestClient = world["client"]
    ada = _cookie(world["ada"].id)
    org_id = world["ada_org"]

    denied = client.post(
        f"/organizations/{org_id}/schedules",
        json={"pipeline": "weekly_report", "weekday": "monday", "hour": 9, "project_id": "proj-1"},
        cookies=_cookie(world["cam"].id),
    )
    assert denied.status_code == 403

    created = client.post(
        f"/organizations/{org_id}/schedules",
        json={"pipeline": "weekly_report", "weekday": "monday", "hour": 9, "project_id": "proj-1"},
        cookies=ada,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["config"] == {
        "pipeline": "weekly_report",
        "weekday": 0,
        "hour": 9,
        "timezone": "Africa/Nairobi",
        "project_id": "proj-1",
    }
    assert world["orgs"].get_timezone(org_id) == "Africa/Nairobi"
    sub = world["subs"].get_subscription(body["subscription_id"])
    assert sub is not None
    assert sub.conversation_id == ""
    assert sub.kind == "weekly_report"
    assert sub.organization_id == org_id
    local = sub.next_check_at.astimezone(ZoneInfo("Africa/Nairobi"))
    assert local.weekday() == 0
    assert local.hour == 9
    assert local.minute == 0

    replaced = client.post(
        f"/organizations/{org_id}/schedules",
        json={
            "pipeline": "weekly_report",
            "weekday": 0,
            "hour": 9,
            "timezone": "America/New_York",
            "project_id": "proj-2",
        },
        cookies=ada,
    )
    assert replaced.status_code == 200, replaced.text
    assert world["orgs"].get_timezone(org_id) == "America/New_York"
    assert replaced.json()["config"]["timezone"] == "America/New_York"


def test_pause_and_cancel_from_the_session_listener(world):
    client: TestClient = world["client"]
    ada = _cookie(world["ada"].id)
    org_id = world["ada_org"]
    conversation = world["convs"].create_conversation(
        title="Launch", user_id=world["ada"].id, organization_id=org_id
    )
    created = client.post(
        f"/organizations/{org_id}/schedules",
        json={"pipeline": "weekly_report", "weekday": "monday", "hour": 9, "timezone": "UTC"},
        cookies=ada,
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]
    subscription_id = created.json()["subscription_id"]

    listed = client.get(f"/conversations/{conversation.id}/sessions", cookies=ada)
    assert listed.status_code == 200, listed.text
    match = next(row for row in listed.json()["sessions"] if row["id"] == session_id)
    assert match["listener_active"] is True
    assert match["subscription_id"] == subscription_id

    paused = client.post(f"/sessions/{session_id}/pause", cookies=ada)
    assert paused.status_code == 200, paused.text
    assert paused.json()["listener_active"] is False
    assert paused.json()["display_status"] == "paused"
    assert world["subs"].get_subscription(subscription_id).status == SubscriptionStatus.PAUSED

    cancelled = client.post(f"/sessions/{session_id}/abort", cookies=ada)
    assert cancelled.status_code == 200, cancelled.text
    assert world["subs"].get_subscription(subscription_id).status == SubscriptionStatus.STOPPED

    started = client.post(f"/sessions/{session_id}/start", cookies=ada)
    assert started.status_code == 200, started.text
    assert started.json()["listener_active"] is True
    assert world["subs"].get_subscription(subscription_id).status == SubscriptionStatus.ACTIVE
