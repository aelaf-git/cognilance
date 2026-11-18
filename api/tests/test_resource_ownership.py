"""Account A cannot read or mutate account B's conversation, run, or session by id."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.routes import conversations, runs, sessions
from core.context.conversations.store import ConversationStore
from core.context.subscriptions import service as subscription_service
from core.context.subscriptions.models import SubscriptionStatus
from core.context.subscriptions.store import SubscriptionStore
from core.runtime.board.store import BoardStore
from core.runtime.missions.models import MissionStatus
from core.runtime.missions.session_type import SessionType
from core.runtime.missions.store import MissionStore
from core.runtime.runs.store import RunStore

USER_A = "account-a"
USER_B = "account-b"


class _EmptyDrafts:
    def get_active_doc(self, conversation_id: str):
        return None


def _as(user_id: str) -> dict[str, str]:
    return {"x-user-id": user_id}


@pytest.fixture
def world(tmp_path, monkeypatch):
    db = str(tmp_path / "coordinator.db")
    conv_store = ConversationStore(db)
    mission_store = MissionStore(db)
    sub_store = SubscriptionStore(db)
    run_store = RunStore(db)
    board_store = BoardStore(db)
    for store in (conv_store, mission_store, sub_store, run_store, board_store):
        store.init_db()

    monkeypatch.setattr(conversations, "conv_store", conv_store)
    monkeypatch.setattr(conversations, "mission_store", mission_store)
    monkeypatch.setattr(conversations, "sub_store", sub_store)
    monkeypatch.setattr(conversations, "DraftStore", _EmptyDrafts)
    monkeypatch.setattr(conversations, "active_document_id", lambda _conversation_id: None)
    monkeypatch.setattr(sessions, "conv_store", conv_store)
    monkeypatch.setattr(sessions, "mission_store", mission_store)
    monkeypatch.setattr(sessions, "sub_store", sub_store)
    monkeypatch.setattr(runs, "run_store", run_store)
    monkeypatch.setattr(runs, "board_store", board_store)
    monkeypatch.setattr(subscription_service, "cancel_mission_for_subscription", lambda *_a, **_k: None)

    conv_a = conv_store.create_conversation(title="A's thread", user_id=USER_A)
    conv_b = conv_store.create_conversation(title="B's thread", user_id=USER_B)
    mission_a = mission_store.create_mission(
        instruction="draft A's note",
        conversation_id=conv_a.id,
        thread_id=conv_a.id,
        user_id=USER_A,
    )
    mission_b = mission_store.create_mission(
        instruction="watch B's inbox",
        conversation_id=conv_b.id,
        thread_id=conv_b.id,
        session_type=SessionType.RECURRING,
        user_id=USER_B,
    )
    run_a = run_store.create_run(
        instruction="A's run",
        thread_id=conv_a.id,
        conversation_id=conv_a.id,
        user_id=USER_A,
    )
    run_b = run_store.create_run(
        instruction="B's private run",
        thread_id=conv_b.id,
        conversation_id=conv_b.id,
        user_id=USER_B,
    )
    run_store.append_step(run_b.id, kind="tool_call", text="B's secret step")
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO board_tasks (
                id, run_id, title, instruction, assignee_role, status,
                depends_on, result_json, result_text, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, '[]', '{}', '', ?, ?)
            """,
            (
                str(uuid.uuid4()),
                run_b.id,
                "B's task",
                "do not show this",
                "researcher",
                "open",
                now,
                now,
            ),
        )
    sub_b = sub_store.create_subscription(
        user_id=USER_B,
        conversation_id=conv_b.id,
        integration="gmail",
        kind="new_email",
        created_from_mission_id=mission_b.id,
    )

    app = FastAPI()

    @app.middleware("http")
    async def identify(request: Request, call_next):
        request.state.user_id = request.headers.get("x-user-id") or ""
        return await call_next(request)

    app.include_router(conversations.router)
    app.include_router(sessions.router)
    app.include_router(runs.router)

    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            missions=mission_store,
            subs=sub_store,
            board=board_store,
            conv_a=conv_a,
            conv_b=conv_b,
            mission_a=mission_a,
            mission_b=mission_b,
            run_a=run_a,
            run_b=run_b,
            sub_b=sub_b,
        )


def test_account_cannot_read_another_accounts_conversation_run_or_session(world):
    client = world.client

    own_conversation = client.get(f"/conversations/{world.conv_a.id}", headers=_as(USER_A))
    assert own_conversation.status_code == 200
    assert own_conversation.json()["id"] == world.conv_a.id
    foreign_conversation = client.get(f"/conversations/{world.conv_b.id}", headers=_as(USER_A))
    assert foreign_conversation.status_code == 404

    own_run = client.get(f"/runs/{world.run_a.id}", headers=_as(USER_A))
    assert own_run.status_code == 200
    assert own_run.json()["run"]["id"] == world.run_a.id
    foreign_run = client.get(f"/runs/{world.run_b.id}", headers=_as(USER_A))
    assert foreign_run.status_code == 404
    assert world.board.list_for_run(world.run_b.id, user_id=USER_A) == []
    assert len(world.board.list_for_run(world.run_b.id, user_id=USER_B)) == 1

    own_session = client.get(f"/sessions/{world.mission_a.id}", headers=_as(USER_A))
    assert own_session.status_code == 200
    assert own_session.json()["session_id"] == world.mission_a.id
    foreign_session = client.get(f"/sessions/{world.mission_b.id}", headers=_as(USER_A))
    assert foreign_session.status_code == 404


def test_account_cannot_abort_or_start_another_accounts_session(world):
    client = world.client

    aborted = client.post(f"/sessions/{world.mission_b.id}/abort", headers=_as(USER_A))
    assert aborted.status_code == 404
    assert world.missions.get_mission(world.mission_b.id).status == MissionStatus.QUEUED

    started = client.post(f"/sessions/{world.mission_b.id}/start", headers=_as(USER_A))
    assert started.status_code == 404
    assert world.missions.get_mission(world.mission_b.id).status == MissionStatus.QUEUED
    assert world.subs.get_subscription(world.sub_b.id).status == SubscriptionStatus.ACTIVE

    own_abort = client.post(f"/sessions/{world.mission_a.id}/abort", headers=_as(USER_A))
    assert own_abort.status_code == 200
    assert world.missions.get_mission(world.mission_a.id).status == MissionStatus.CANCELLED

    own_start = client.post(f"/sessions/{world.mission_b.id}/start", headers=_as(USER_B))
    assert own_start.status_code == 200
    assert world.missions.get_mission(world.mission_b.id).status == MissionStatus.RUNNING


def test_session_list_hides_other_accounts_and_foreign_conversations(world):
    client = world.client

    listed = client.get("/sessions", headers=_as(USER_A))
    assert listed.status_code == 200
    ids = {session["session_id"] for session in listed.json()["sessions"]}
    assert world.mission_a.id in ids
    assert world.mission_b.id not in ids

    foreign_conversation = client.get(
        "/sessions",
        params={"conversation_id": world.conv_b.id},
        headers=_as(USER_A),
    )
    assert foreign_conversation.status_code == 404

    own_conversation = client.get(
        "/sessions",
        params={"conversation_id": world.conv_b.id},
        headers=_as(USER_B),
    )
    assert own_conversation.status_code == 200
    own_ids = {session["session_id"] for session in own_conversation.json()["sessions"]}
    assert own_ids == {world.mission_b.id}


def test_account_cannot_stop_another_accounts_subscription(world):
    client = world.client

    denied = client.post(f"/subscriptions/{world.sub_b.id}/stop", headers=_as(USER_A))
    assert denied.status_code == 404
    assert world.subs.get_subscription(world.sub_b.id).status == SubscriptionStatus.ACTIVE

    stopped = client.post(f"/subscriptions/{world.sub_b.id}/stop", headers=_as(USER_B))
    assert stopped.status_code == 200
    assert world.subs.get_subscription(world.sub_b.id).status == SubscriptionStatus.STOPPED


def test_unknown_uuid_is_not_found(world):
    missing = str(uuid.uuid4())
    client = world.client
    headers = _as(USER_A)
    assert client.get(f"/runs/{missing}", headers=headers).status_code == 404
    assert client.get(f"/sessions/{missing}", headers=headers).status_code == 404
    assert client.post(f"/sessions/{missing}/abort", headers=headers).status_code == 404
