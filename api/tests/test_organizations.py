"""Each account gets one personal organization, and conversations follow it."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from api.auth.guard import is_public_request
from api.auth.session import get_user_id
from api.routes import auth, conversations
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.request import current_user_id, current_user_timezone
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.accounts import AccountStore
from core.context.users.store import UserPreferencesStore
from core.context.users.timezone import activate_user_timezone, client_timezone_from_request
from core.runtime.missions.store import MissionStore


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")

    accounts = AccountStore(db)
    orgs = OrgStore(db)
    prefs = UserPreferencesStore(db)
    conv_store = ConversationStore(db)
    mission_store = MissionStore(db)
    sub_store = SubscriptionStore(db)
    for store in (accounts, orgs, prefs, conv_store, mission_store, sub_store):
        store.init_db()

    monkeypatch.setattr(auth, "account_store", accounts)
    monkeypatch.setattr("api.deps.account_store", accounts)
    monkeypatch.setattr("api.deps.org_store", orgs)
    monkeypatch.setattr("core.context.users.timezone._store", prefs)
    monkeypatch.setattr(conversations, "conv_store", conv_store)
    monkeypatch.setattr(conversations, "mission_store", mission_store)
    monkeypatch.setattr(conversations, "sub_store", sub_store)
    monkeypatch.setattr(
        conversations,
        "DraftStore",
        lambda: type("D", (), {"get_active_doc": lambda self, _id: None})(),
    )
    monkeypatch.setattr(conversations, "active_document_id", lambda _id: None)

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
    app.include_router(conversations.router)

    with TestClient(app) as client:
        yield {"client": client, "accounts": accounts, "orgs": orgs, "convs": conv_store, "db": db}


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password1", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_register_creates_one_owner_organization(world):
    profile = _register(world["client"], "ada@example.com")
    memberships = world["orgs"].memberships_for(profile["id"])
    assert len(memberships) == 1
    assert memberships[0].role == "owner"
    assert world["orgs"].active_for_account(profile["id"]) == memberships[0].organization_id


def test_conversation_list_is_limited_to_the_callers_organization(world):
    client = world["client"]
    ada = _register(client, "ada@example.com")
    ada_conv = client.post("/conversations")
    assert ada_conv.status_code == 200
    ada_id = ada_conv.json()["id"]

    client.cookies.clear()
    _register(client, "grace@example.com")
    grace_list = client.get("/conversations")
    assert grace_list.status_code == 200
    assert grace_list.json()["conversations"] == []
    grace_conv = client.post("/conversations")
    assert grace_conv.status_code == 200

    client.cookies.clear()
    logged_in = client.post(
        "/auth/login",
        json={"email": "ada@example.com", "password": "password1"},
    )
    assert logged_in.status_code == 200
    listed = client.get("/conversations")
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()["conversations"]]
    assert ids == [ada_id]
    grace = world["accounts"].get_by_email("grace@example.com")
    assert grace is not None
    assert world["orgs"].active_for_account(ada["id"]) != world["orgs"].active_for_account(grace.id)


def test_backfill_stamps_an_existing_account_conversation(world):
    account = world["accounts"].create(
        email="old@example.com",
        password="password1",
        display_name="Old Account",
    )
    with sqlite3.connect(world["db"]) as conn:
        conn.execute("DELETE FROM memberships")
        conn.execute("DELETE FROM organizations")
    conversation = world["convs"].create_conversation(user_id=account.id)
    assert conversation.organization_id is None

    world["orgs"].backfill()

    org_id = world["orgs"].active_for_account(account.id)
    memberships = world["orgs"].memberships_for(account.id)
    assert org_id
    assert len(memberships) == 1
    assert memberships[0].role == "owner"
    loaded = world["convs"].get_conversation(conversation.id)
    assert loaded is not None
    assert loaded.organization_id == org_id
