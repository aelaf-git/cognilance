"""GitHub is an organization grant: admins connect it, members only see status."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.responses import Response

from api import deps
from api.auth.guard import is_public_request
from api.auth.session import COOKIE_NAME, set_user_cookie
from api.routes import integrations, organizations
from core.broker.crypto import _fernet
from core.broker.oauth import OAuthService
from core.broker.store import IntegrationStore
from core.broker.token_manager import TokenManager
from core.context.orgs.store import OrgStore
from core.context.request import current_mission_id, current_user_id
from core.context.users.accounts import AccountStore
from core.runtime.runs.store import RunStore

TOKEN = "ghp_test_secret"


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")
    monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
    _fernet.cache_clear()

    accounts = AccountStore(db)
    orgs = OrgStore(db)
    runs = RunStore(db)
    store = IntegrationStore(db)
    for ready in (accounts, orgs, runs, store):
        ready.init_db()
    service = OAuthService(store)

    ada = accounts.create(email="ada@example.com", password="password1", display_name="Ada")
    bea = accounts.create(email="bea@example.com", password="password1", display_name="Bea")
    cam = accounts.create(email="cam@example.com", password="password1", display_name="Cam")
    ada_org = orgs.active_for_account(ada.id)
    bea_org = orgs.active_for_account(bea.id)
    cam_org = orgs.active_for_account(cam.id)
    assert ada_org and bea_org and cam_org
    orgs.add_membership(ada_org, cam.id, "member")
    orgs.delete_organization(cam_org)
    assert orgs.active_for_account(cam.id) == ada_org

    monkeypatch.setattr(deps, "org_store", orgs)
    monkeypatch.setattr(deps, "oauth_service", service)

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

    app.include_router(integrations.router)
    app.include_router(organizations.router)
    return {
        "db": db,
        "store": store,
        "service": service,
        "orgs": orgs,
        "runs": runs,
        "ada": ada,
        "bea": bea,
        "cam": cam,
        "ada_org": ada_org,
        "bea_org": bea_org,
        "client": TestClient(app),
    }


def _cookie(user_id: str) -> dict[str, str]:
    response = Response()
    set_user_cookie(response, user_id)
    header = response.headers["set-cookie"]
    value = header.split(";", 1)[0].split("=", 1)[1]
    return {COOKIE_NAME: value}


def _github(payload: dict) -> dict:
    rows = payload.get("integrations") or payload.get("apps") or []
    return next(row for row in rows if row["id"] == "github")


def _assert_hidden(text: str) -> None:
    assert TOKEN not in text


def test_github_stays_coming_soon_until_both_credentials_exist(world, monkeypatch):
    client: TestClient = world["client"]
    ada = _cookie(world["ada"].id)

    hidden = client.get("/integrations/list", cookies=ada)
    assert hidden.status_code == 200
    github = _github(hidden.json())
    assert github["coming_soon"] is True
    assert github["connected"] is False
    assert github["actions"] == []
    _assert_hidden(hidden.text)

    refused = client.get("/integrations/github/connect", cookies=ada, follow_redirects=False)
    assert refused.status_code == 404
    _assert_hidden(refused.text)

    monkeypatch.setenv("GITHUB_CLIENT_ID", "client-id")
    still_hidden = client.get("/integrations/list", cookies=ada)
    assert _github(still_hidden.json())["coming_soon"] is True


def test_admin_connects_and_member_cannot_replace_the_grant(world, monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "client-secret")
    client: TestClient = world["client"]
    ada = _cookie(world["ada"].id)
    cam = _cookie(world["cam"].id)
    bea = _cookie(world["bea"].id)

    ready = client.get("/integrations/list", cookies=ada)
    github = _github(ready.json())
    assert github["coming_soon"] is False
    assert github["connected"] is False
    assert github["manage"] is True
    assert "list_repositories" in github["actions"]
    _assert_hidden(ready.text)

    started = client.get("/integrations/github/connect", cookies=ada, follow_redirects=False)
    assert started.status_code == 307
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    _assert_hidden(started.headers["location"])

    async def exchange(_code: str) -> dict:
        return {
            "access_token": TOKEN,
            "refresh_token": None,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
        }

    monkeypatch.setattr(world["service"], "_exchange_github", exchange)
    callback = client.get("/integrations/oauth/callback", params={"code": "code", "state": state})
    assert callback.status_code == 200
    assert callback.json() == {"connected": "github"}
    _assert_hidden(callback.text)

    store: IntegrationStore = world["store"]
    grant = store.get_org_grant(world["ada_org"], "github")
    assert grant is not None
    assert grant.access_token == TOKEN
    with sqlite3.connect(world["db"]) as conn:
        ciphertext = conn.execute(
            "SELECT access_token_enc FROM integrations WHERE organization_id = ?",
            (world["ada_org"],),
        ).fetchone()[0]
    assert ciphertext != TOKEN
    assert TOKEN not in ciphertext

    connected = client.get("/integrations/list", cookies=ada)
    assert _github(connected.json())["connected"] is True
    _assert_hidden(connected.text)

    async def list_repositories(self, integration_id, access_token, action, params):
        assert integration_id == "github"
        assert action == "list_repositories"
        assert access_token == TOKEN
        return [
            {
                "id": 101,
                "full_name": "ada/widgets",
                "html_url": "https://github.com/ada/widgets",
            },
            {
                "id": 202,
                "full_name": "ada/other",
                "html_url": "https://github.com/ada/other",
            },
        ]

    monkeypatch.setattr(
        "core.broker.executor.IntegrationExecutor.execute", list_repositories
    )
    repos = client.get("/integrations/github/repos", cookies=ada)
    assert repos.status_code == 200
    assert repos.json()["repos"] == [
        {
            "id": "101",
            "name": "ada/widgets",
            "url": "https://github.com/ada/widgets",
            "selected": False,
        },
        {
            "id": "202",
            "name": "ada/other",
            "url": "https://github.com/ada/other",
            "selected": False,
        },
    ]
    _assert_hidden(repos.text)

    saved = client.put(
        "/integrations/github/repos",
        cookies=ada,
        json={"repo_ids": ["101", "999"]},
    )
    assert saved.status_code == 200
    assert saved.json() == {"repo_ids": ["101"]}
    _assert_hidden(saved.text)
    assert store.get_org_grant(world["ada_org"], "github").selected_repos == ["101"]

    chosen = client.get("/integrations/github/repos", cookies=ada)
    selected = {row["id"]: row["selected"] for row in chosen.json()["repos"]}
    assert selected == {"101": True, "202": False}
    _assert_hidden(chosen.text)

    member_list = client.get("/integrations/list", cookies=cam)
    member_github = _github(member_list.json())
    assert member_github["connected"] is True
    assert member_github["manage"] is False
    assert member_github["selected_repos"] == ["101"]
    _assert_hidden(member_list.text)

    assert client.get(
        "/integrations/github/connect", cookies=cam, follow_redirects=False
    ).status_code == 403
    assert client.put(
        "/integrations/github/repos", cookies=cam, json={"repo_ids": ["202"]}
    ).status_code == 403
    denied = client.post("/integrations/github/disconnect", cookies=cam)
    assert denied.status_code == 403
    _assert_hidden(denied.text)
    assert store.is_org_connected(world["ada_org"], "github")

    outsider = client.get("/integrations/list", cookies=bea)
    assert _github(outsider.json())["connected"] is False
    _assert_hidden(outsider.text)
    org_view = client.get(
        f"/organizations/{world['ada_org']}/integrations", cookies=bea
    )
    assert org_view.status_code == 404

    tokens = TokenManager(store=store, oauth=world["service"])
    assert tokens.is_connected(world["cam"].id, "github") is True
    assert tokens.is_connected(world["bea"].id, "github") is False
    run = world["runs"].create_run(
        instruction="collect",
        thread_id="thread",
        user_id=world["bea"].id,
        organization_id=world["ada_org"],
    )
    mission = current_mission_id.set(run.id)
    try:
        assert tokens.is_connected(world["bea"].id, "github") is True
    finally:
        current_mission_id.reset(mission)

    disconnected = client.post("/integrations/github/disconnect", cookies=ada)
    assert disconnected.status_code == 200
    assert disconnected.json()["connected"] is False
    _assert_hidden(disconnected.text)
    assert store.get_org_grant(world["ada_org"], "github") is None
    after = client.get("/integrations/list", cookies=cam)
    assert _github(after.json())["connected"] is False
    _assert_hidden(after.text)
