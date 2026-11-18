"""Register/login cookies replace anonymous UUID minting."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from api.auth.guard import is_public_request
from api.auth.session import COOKIE_NAME, get_user_id
from api.routes import auth, conversations
from core.context.conversations.store import ConversationStore
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
    prefs = UserPreferencesStore(db)
    conv_store = ConversationStore(db)
    mission_store = MissionStore(db)
    sub_store = SubscriptionStore(db)
    for store in (accounts, prefs, conv_store, mission_store, sub_store):
        store.init_db()

    monkeypatch.setattr(auth, "account_store", accounts)
    monkeypatch.setattr("api.deps.account_store", accounts)
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
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )
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
        yield {
            "client": client,
            "accounts": accounts,
            "prefs": prefs,
            "convs": conv_store,
        }


def _register(client: TestClient, email: str, password: str = "password1") -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200, response.text
    assert COOKIE_NAME in response.cookies
    return response.json()


def test_register_sets_cookie_and_me_works(world):
    client = world["client"]
    profile = _register(client, "alice@example.com")
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == profile["id"]
    assert me.json()["email"] == "alice@example.com"


def test_login_wrong_password_is_unauthorized(world):
    client = world["client"]
    _register(client, "bob@example.com")
    client.cookies.clear()
    denied = client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "wrong-password"},
    )
    assert denied.status_code == 401


def test_no_cookie_cannot_list_conversations(world):
    client = world["client"]
    response = client.get("/conversations")
    assert response.status_code == 401


def test_accounts_cannot_list_each_others_conversations(world):
    client = world["client"]
    alice = _register(client, "alice@example.com")
    created = client.post("/conversations")
    assert created.status_code == 200
    alice_conv = created.json()["id"]
    world["convs"].create_conversation(user_id=alice["id"])  # ensure ownership stamp

    client.cookies.clear()
    _register(client, "carol@example.com")
    listed = client.get("/conversations")
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["conversations"]}
    assert alice_conv not in ids


def test_logout_clears_access(world):
    client = world["client"]
    _register(client, "dave@example.com")
    assert client.get("/auth/me").status_code == 200
    logged_out = client.post("/auth/logout")
    assert logged_out.status_code == 200
    client.cookies.clear()
    assert client.get("/auth/me").status_code == 401
    assert client.get("/conversations").status_code == 401


def test_change_password_then_login_with_new_password(world):
    client = world["client"]
    _register(client, "frank@example.com", "password1")
    changed = client.post(
        "/auth/password",
        json={"current_password": "password1", "new_password": "password2"},
    )
    assert changed.status_code == 200
    assert changed.json()["updated"] is True
    client.cookies.clear()
    old = client.post(
        "/auth/login",
        json={"email": "frank@example.com", "password": "password1"},
    )
    assert old.status_code == 401
    new = client.post(
        "/auth/login",
        json={"email": "frank@example.com", "password": "password2"},
    )
    assert new.status_code == 200
    assert client.get("/auth/me").json()["email"] == "frank@example.com"


def test_change_password_rejects_wrong_current_password(world):
    client = world["client"]
    _register(client, "gina@example.com", "password1")
    denied = client.post(
        "/auth/password",
        json={"current_password": "not-the-password", "new_password": "password2"},
    )
    assert denied.status_code == 400
    assert denied.json()["detail"] == "Current password is incorrect"
    client.cookies.clear()
    still = client.post(
        "/auth/login",
        json={"email": "gina@example.com", "password": "password1"},
    )
    assert still.status_code == 200


def test_patch_me_timezone_uses_preferences_store(world):
    client = world["client"]
    profile = _register(client, "erin@example.com")
    patched = client.patch("/auth/me", json={"timezone": "America/New_York"})
    assert patched.status_code == 200
    assert patched.json()["timezone"] == "America/New_York"
    assert world["prefs"].get_timezone(profile["id"]) == "America/New_York"
