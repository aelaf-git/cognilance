"""Feedback on a run stays with that run and names the specialist who produced it."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.routes import runs
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.users.accounts import AccountStore
from core.runtime.board.store import BoardStore
from core.runtime.runs.models import RunStatus
from core.runtime.runs.store import RunStore


ORIGINAL = "The launch note says the brief is ready."
REVISION = "The launch note says the brief still needs a date."


def _as(user_id: str) -> dict[str, str]:
    return {"x-user-id": user_id}


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    accounts = AccountStore(db)
    orgs = OrgStore(db)
    run_store = RunStore(db)
    board = BoardStore(db)
    conv_store = ConversationStore(db)
    for store in (accounts, orgs, run_store, board, conv_store):
        store.init_db()

    ada = accounts.create(email="ada@example.com", password="password1", display_name="Ada")
    bea = accounts.create(email="bea@example.com", password="password1", display_name="Bea")
    ada_org = orgs.active_for_account(ada.id)
    bea_org = orgs.active_for_account(bea.id)
    assert ada_org and bea_org and ada_org != bea_org

    monkeypatch.setattr("api.deps.org_store", orgs)
    monkeypatch.setattr(runs, "run_store", run_store)
    monkeypatch.setattr(runs, "board_store", board)
    monkeypatch.setattr(runs, "conv_store", conv_store)

    app = FastAPI()

    @app.middleware("http")
    async def identify(request: Request, call_next):
        request.state.user_id = request.headers.get("x-user-id") or ""
        return await call_next(request)

    app.include_router(runs.router)
    return {
        "client": TestClient(app),
        "runs": run_store,
        "board": board,
        "conversations": conv_store,
        "ada": ada,
        "bea": bea,
        "ada_org": ada_org,
    }


def _run_with_output(world) -> str:
    conversation = world["conversations"].create_conversation(
        title="Launch",
        user_id=world["ada"].id,
        organization_id=world["ada_org"],
    )
    world["conversations"].append_message(
        conversation.id,
        role="assistant",
        content="An earlier draft.",
    )
    world["conversations"].append_message(
        conversation.id,
        role="assistant",
        content=ORIGINAL,
    )
    run = world["runs"].create_run(
        instruction="Write the launch note",
        thread_id=conversation.id,
        conversation_id=conversation.id,
        user_id=world["ada"].id,
        organization_id=world["ada_org"],
        run_id="run-feedback",
    )
    world["runs"].update_status(run.id, RunStatus.COMPLETED, result_text=ORIGINAL)
    task = world["board"].create_task(
        run_id=run.id,
        title="Launch note",
        instruction="Write the launch note",
        assignee_role="project_agent",
    )
    world["board"].complete_task(task.id, result_text=ORIGINAL)
    return run.id


def test_a_thumbs_down_with_an_edit_is_readable_from_the_run(world):
    run_id = _run_with_output(world)
    client: TestClient = world["client"]
    posted = client.post(
        f"/runs/{run_id}/feedback",
        json={
            "rating": -1,
            "note": "The date is missing.",
            "revision": REVISION,
        },
        headers=_as(world["ada"].id),
    )
    assert posted.status_code == 200, posted.text

    shown = client.get(f"/runs/{run_id}", headers=_as(world["ada"].id))
    assert shown.status_code == 200, shown.text
    steps = [step for step in shown.json()["steps"] if step["kind"] == "feedback"]
    assert len(steps) == 1
    assert steps[0]["text"] == "The date is missing."
    assert steps[0]["data"]["rating"] == -1
    assert steps[0]["data"]["message"] == ORIGINAL
    assert steps[0]["data"]["revision"] == REVISION
    assert steps[0]["data"]["agent_id"] == "project_agent"


def test_another_organization_cannot_post_feedback(world):
    run_id = _run_with_output(world)
    client: TestClient = world["client"]
    denied = client.post(
        f"/runs/{run_id}/feedback",
        json={"rating": -1, "note": "Not our run.", "revision": REVISION},
        headers=_as(world["bea"].id),
    )
    assert denied.status_code == 404
    shown = client.get(f"/runs/{run_id}", headers=_as(world["ada"].id))
    assert [step for step in shown.json()["steps"] if step["kind"] == "feedback"] == []
