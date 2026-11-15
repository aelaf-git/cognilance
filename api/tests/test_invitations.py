"""Owners invite by email. Members cannot administer the organization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from api.auth.guard import is_public_request
from api.auth.session import get_user_id
from api.routes import auth, organizations
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.request import current_user_id, current_user_timezone
from core.context.users.accounts import AccountStore
from core.context.users.store import UserPreferencesStore
from core.context.users.timezone import activate_user_timezone, client_timezone_from_request
from core.runtime.runs.store import RunStore


class _Connections:
    def list_for_user(self, user_id: str) -> list:
        return []


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")

    accounts = AccountStore(db)
    orgs = OrgStore(db)
    prefs = UserPreferencesStore(db)
    conv_store = ConversationStore(db)
    run_store = RunStore(db)
    for store in (accounts, orgs, prefs, conv_store, run_store):
        store.init_db()

    monkeypatch.setattr(auth, "account_store", accounts)
    monkeypatch.setattr("api.deps.account_store", accounts)
    monkeypatch.setattr("api.deps.org_store", orgs)
    monkeypatch.setattr("core.context.users.timezone._store", prefs)
    monkeypatch.setattr("api.deps.conv_store", conv_store)
    monkeypatch.setattr("api.deps.run_store", run_store)
    monkeypatch.setattr("api.deps.oauth_service", _Connections())

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
    app.include_router(organizations.router)

    with TestClient(app) as client:
        yield {"client": client, "accounts": accounts, "orgs": orgs, "db": db}


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password1", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _login(client: TestClient, email: str) -> None:
    client.cookies.clear()
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "password1"},
    )
    assert response.status_code == 200, response.text


def _membership_count(db: str, organization_id: str, account_id: str) -> int:
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM memberships
            WHERE organization_id = ? AND account_id = ?
            """,
            (organization_id, account_id),
        ).fetchone()
    return int(row[0])


def test_owner_invite_is_accepted_once(world):
    client = world["client"]
    owner = _register(client, "owner@example.com")
    org_id = world["orgs"].active_for_account(owner["id"])
    _register(client, "guest@example.com")
    _login(client, "owner@example.com")

    created = client.post(
        f"/organizations/{org_id}/invitations",
        json={"email": "guest@example.com"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["role"] == "member"
    token = created.json()["token"]

    _login(client, "guest@example.com")
    accepted = client.post(f"/invitations/{token}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "member"
    guest = world["accounts"].get_by_email("guest@example.com")
    assert guest is not None
    assert _membership_count(world["db"], org_id, guest.id) == 1

    again = client.post(f"/invitations/{token}/accept")
    assert again.status_code == 200, again.text
    assert _membership_count(world["db"], org_id, guest.id) == 1
    assert again.json()["role"] == "member"


def test_member_is_forbidden_and_admin_can_invite(world):
    client = world["client"]
    owner = _register(client, "owner@example.com")
    org_id = world["orgs"].active_for_account(owner["id"])
    _register(client, "guest@example.com")
    _login(client, "owner@example.com")
    created = client.post(
        f"/organizations/{org_id}/invitations",
        json={"email": "guest@example.com", "role": "member"},
    )
    assert created.status_code == 200, created.text
    _login(client, "guest@example.com")
    assert client.post(f"/invitations/{created.json()['token']}/accept").status_code == 200

    forbidden = client.post(
        f"/organizations/{org_id}/invitations",
        json={"email": "other@example.com"},
    )
    assert forbidden.status_code == 403
    assert client.delete(f"/organizations/{org_id}").status_code == 403

    admin = _register(client, "admin@example.com")
    world["orgs"].add_membership(org_id, admin["id"], "admin")
    invited = client.post(
        f"/organizations/{org_id}/invitations",
        json={"email": "other@example.com"},
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["role"] == "member"

    _login(client, "owner@example.com")
    deleted = client.delete(f"/organizations/{org_id}")
    assert deleted.status_code == 200, deleted.text
    assert world["orgs"].get_organization(org_id) is None
    assert world["orgs"].membership_for(owner["id"], org_id) is None


def test_outsider_cannot_see_organization_resources(world):
    client = world["client"]
    owner = _register(client, "owner@example.com")
    org_id = world["orgs"].active_for_account(owner["id"])
    for path in ("conversations", "runs", "integrations"):
        visible = client.get(f"/organizations/{org_id}/{path}")
        assert visible.status_code == 200, visible.text

    _register(client, "outsider@example.com")
    for path in ("conversations", "runs", "integrations"):
        hidden = client.get(f"/organizations/{org_id}/{path}")
        assert hidden.status_code == 404, hidden.text
