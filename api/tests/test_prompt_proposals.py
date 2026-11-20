"""A prompt proposal changes one organization only after an admin approves it."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.responses import Response

from api.auth.guard import is_public_request
from api.auth.session import COOKIE_NAME, set_user_cookie
from api.routes import organizations
from core.context.orgs.store import OrgStore
from core.context.request import current_user_id
from core.context.users.accounts import AccountStore
from pipelines.coordinator_board.coordinator import _plan_prompt, _roster

PROPOSED = "Always mention the launch date."
PREVIOUS = "Sign off as Ada."


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")
    accounts = AccountStore(db)
    orgs = OrgStore(db)
    for store in (accounts, orgs):
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
    monkeypatch.setattr("api.deps.org_store", orgs)

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
    return {
        "client": TestClient(app),
        "orgs": orgs,
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


def _prompt(organization_id: str) -> str:
    return _plan_prompt("Draft a note", roles=_roster(organization_id))


def test_pending_approval_and_restore_stay_inside_one_organization(world):
    orgs: OrgStore = world["orgs"]
    client: TestClient = world["client"]
    ada = _cookie(world["ada"].id)
    orgs.set_agent_setting(world["ada_org"], "email_agent", enabled=True, extra_instruction=PREVIOUS)

    created = client.post(
        f"/organizations/{world['ada_org']}/prompt-proposals",
        json={
            "agent_id": "email_agent",
            "proposed_text": PROPOSED,
            "evidence_run_ids": ["run-a", "run-b"],
        },
        cookies=ada,
    )
    assert created.status_code == 200, created.text
    proposal = created.json()
    assert proposal["status"] == "pending"
    assert proposal["current_text"] == PREVIOUS
    assert proposal["evidence_run_ids"] == ["run-a", "run-b"]
    assert PROPOSED not in _prompt(world["ada_org"])
    assert orgs.extra_instructions(world["ada_org"])["email_agent"] == PREVIOUS

    denied = client.post(
        f"/organizations/{world['ada_org']}/prompt-proposals/{proposal['id']}/decision",
        json={"approved": True},
        cookies=_cookie(world["cam"].id),
    )
    assert denied.status_code == 403
    hidden = client.post(
        f"/organizations/{world['bea_org']}/prompt-proposals/{proposal['id']}/decision",
        json={"approved": True},
        cookies=_cookie(world["bea"].id),
    )
    assert hidden.status_code == 404

    approved = client.post(
        f"/organizations/{world['ada_org']}/prompt-proposals/{proposal['id']}/decision",
        json={"approved": True},
        cookies=ada,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["previous_text"] == PREVIOUS
    ada_prompt = _prompt(world["ada_org"])
    bea_prompt = _prompt(world["bea_org"])
    assert PROPOSED in ada_prompt
    assert PROPOSED not in bea_prompt

    restored = client.post(
        f"/organizations/{world['ada_org']}/prompt-proposals/{proposal['id']}/restore",
        cookies=ada,
    )
    assert restored.status_code == 200, restored.text
    after = _prompt(world["ada_org"])
    assert PROPOSED not in after
    assert PREVIOUS in after
    events = [
        event
        for event in orgs.list_events(world["ada_org"])
        if event.type == "prompt.restored"
    ]
    assert len(events) == 1
    assert events[0].payload["text"] == PREVIOUS
    assert events[0].organization_id == world["ada_org"]
    assert orgs.list_events(world["bea_org"]) == []


def test_reject_leaves_the_instruction_and_approval_keeps_a_disabled_agent(world):
    orgs: OrgStore = world["orgs"]
    client: TestClient = world["client"]
    ada = _cookie(world["ada"].id)
    orgs.set_agent_setting(world["ada_org"], "researcher", enabled=False)

    rejected_row = client.post(
        f"/organizations/{world['ada_org']}/prompt-proposals",
        json={"agent_id": "researcher", "proposed_text": "Cite the source.", "evidence_run_ids": []},
        cookies=ada,
    )
    assert rejected_row.status_code == 200, rejected_row.text
    rejected = client.post(
        f"/organizations/{world['ada_org']}/prompt-proposals/{rejected_row.json()['id']}/decision",
        json={"approved": False},
        cookies=ada,
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert "researcher" not in orgs.extra_instructions(world["ada_org"])
    assert "Cite the source." not in _prompt(world["ada_org"])

    approved_row = client.post(
        f"/organizations/{world['ada_org']}/prompt-proposals",
        json={"agent_id": "researcher", "proposed_text": "Name the owner.", "evidence_run_ids": []},
        cookies=ada,
    )
    assert approved_row.status_code == 200, approved_row.text
    approved = client.post(
        f"/organizations/{world['ada_org']}/prompt-proposals/{approved_row.json()['id']}/decision",
        json={"approved": True},
        cookies=ada,
    )
    assert approved.status_code == 200, approved.text
    assert "researcher" in orgs.disabled_agent_ids(world["ada_org"])
    assert orgs.extra_instructions(world["ada_org"])["researcher"] == "Name the owner."
    assert "Name the owner." not in _prompt(world["ada_org"])
