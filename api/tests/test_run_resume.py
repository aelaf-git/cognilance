"""A run can be resumed after approval or restart, and cancelled with its mission."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.types import Command

from api.deps import register_mission_task
from api.routes import chat, runs
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.users.accounts import AccountStore
from core.runtime.board.store import BoardStore
from core.runtime.missions.models import MissionStatus
from core.runtime.missions.store import MissionStore
from core.runtime.runner import recover_interrupted_runs
from core.runtime.runs.models import RunStatus
from core.runtime.runs.store import RunStore


def _as(user_id: str) -> dict[str, str]:
    return {"x-user-id": user_id}


class _LiveTask:
    def __init__(self) -> None:
        self.did_cancel = False

    def done(self) -> bool:
        return False

    def cancel(self) -> bool:
        self.did_cancel = True
        return True

    def add_done_callback(self, _fn) -> None:
        return None


class _Graph:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def aget_state(self, config):
        return SimpleNamespace(next=(), interrupts=(), values={})

    async def astream(self, graph_input, config, stream_mode=None):
        self.calls.append({"input": graph_input, "config": config})
        yield "values", {"messages": [AIMessage(content="continued")]}


def _app(*routers) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def identify(request: Request, call_next):
        request.state.user_id = request.headers.get("x-user-id") or ""
        return await call_next(request)

    for router in routers:
        app.include_router(router)
    return app


@pytest.fixture
def world(tmp_path, monkeypatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    accounts = AccountStore(db)
    orgs = OrgStore(db)
    missions = MissionStore(db)
    run_store = RunStore(db)
    board = BoardStore(db)
    conv_store = ConversationStore(db)
    for store in (accounts, orgs, missions, run_store, board, conv_store):
        store.init_db()

    ada = accounts.create(email="ada@example.com", password="password1", display_name="Ada")
    grace = accounts.create(email="grace@example.com", password="password1", display_name="Grace")
    bea = accounts.create(email="bea@example.com", password="password1", display_name="Bea")
    ada_org = orgs.active_for_account(ada.id)
    assert ada_org
    orgs.add_membership(ada_org, grace.id, "member")

    monkeypatch.setattr("api.deps.org_store", orgs)
    monkeypatch.setattr("api.deps.account_store", accounts)
    monkeypatch.setattr(runs, "run_store", run_store)
    monkeypatch.setattr(runs, "mission_store", missions)
    monkeypatch.setattr(runs, "board_store", board)
    monkeypatch.setattr(chat, "run_store", run_store)
    monkeypatch.setattr(chat, "mission_store", missions)
    monkeypatch.setattr(chat, "conv_store", conv_store)
    monkeypatch.setattr(chat, "sub_store", SimpleNamespace(list_notifications=lambda *a, **k: []))

    async def title(text: str) -> str:
        return text[:40]

    monkeypatch.setattr(chat, "paraphrase_conversation_title", title)
    graph = _Graph()

    async def ensure_graph(*, with_checkpointer: bool = True):
        return graph

    monkeypatch.setattr("core.runtime.runner.ensure_graph", ensure_graph)
    return SimpleNamespace(
        accounts=accounts,
        orgs=orgs,
        missions=missions,
        runs=run_store,
        board=board,
        conversations=conv_store,
        ada=ada,
        grace=grace,
        bea=bea,
        ada_org=ada_org,
        graph=graph,
        client=TestClient(_app(runs.router, chat.router)),
    )


def test_waiting_run_survives_restart_and_resume_uses_its_thread(world):
    running = world.missions.create_mission(
        instruction="Keep going",
        thread_id="thread-running",
        user_id=world.ada.id,
        organization_id=world.ada_org,
    )
    world.missions.update_status(running.id, MissionStatus.RUNNING)
    world.runs.create_run(
        instruction="Keep going",
        thread_id="thread-running",
        conversation_id="thread-running",
        user_id=world.ada.id,
        organization_id=world.ada_org,
        mission_id=running.id,
        run_id=running.id,
    )
    world.runs.update_status(running.id, RunStatus.RUNNING)

    waiting = world.missions.create_mission(
        instruction="Send the note",
        thread_id="thread-waiting",
        user_id=world.ada.id,
        organization_id=world.ada_org,
    )
    world.missions.update_status(waiting.id, MissionStatus.RUNNING)
    world.runs.create_run(
        instruction="Send the note",
        thread_id="thread-waiting",
        conversation_id="thread-waiting",
        user_id=world.ada.id,
        organization_id=world.ada_org,
        mission_id=waiting.id,
        run_id=waiting.id,
    )
    world.runs.update_status(
        waiting.id,
        RunStatus.WAITING_APPROVAL,
        pending_approval={"tool": "gmail.send", "approved": False},
    )

    recover_interrupted_runs()
    assert world.runs.get_run(running.id).status == RunStatus.QUEUED
    assert world.missions.get_mission(running.id).status == MissionStatus.QUEUED
    assert world.runs.get_run(waiting.id).status == RunStatus.WAITING_APPROVAL
    assert world.missions.get_mission(waiting.id).status == MissionStatus.WAITING_APPROVAL

    live = _LiveTask()
    register_mission_task(waiting.id, live)
    try:
        blocked = world.client.post(f"/runs/{waiting.id}/resume", headers=_as(world.ada.id))
        assert blocked.status_code == 409
        assert live.did_cancel is False
    finally:
        from api.deps import _running_mission_tasks

        _running_mission_tasks.pop(waiting.id, None)

    resumed = world.client.post(f"/runs/{waiting.id}/resume", headers=_as(world.ada.id))
    assert resumed.status_code == 200
    assert world.graph.calls
    call = world.graph.calls[0]
    assert call["config"]["configurable"]["thread_id"] == "thread-waiting"
    assert isinstance(call["input"], Command)
    assert call["input"].resume == {"approved": True}

    again = world.client.post(f"/runs/{waiting.id}/resume", headers=_as(world.ada.id))
    assert again.status_code == 409


def test_cancel_stops_the_running_mission(world):
    mission = world.missions.create_mission(
        instruction="Work",
        thread_id="thread-cancel",
        user_id=world.ada.id,
        organization_id=world.ada_org,
    )
    world.missions.update_status(mission.id, MissionStatus.RUNNING)
    world.runs.create_run(
        instruction="Work",
        thread_id="thread-cancel",
        conversation_id="thread-cancel",
        user_id=world.ada.id,
        organization_id=world.ada_org,
        mission_id=mission.id,
        run_id=mission.id,
    )
    world.runs.update_status(mission.id, RunStatus.RUNNING)
    live = _LiveTask()
    register_mission_task(mission.id, live)
    try:
        denied = world.client.post(f"/runs/{mission.id}/cancel", headers=_as(world.bea.id))
        assert denied.status_code == 404
        assert world.missions.get_mission(mission.id).status == MissionStatus.RUNNING
        assert live.did_cancel is False

        cancelled = world.client.post(f"/runs/{mission.id}/cancel", headers=_as(world.ada.id))
        assert cancelled.status_code == 200
        assert cancelled.json()["task_cancelled"] is True
        assert live.did_cancel is True
        assert world.runs.get_run(mission.id).status == RunStatus.CANCELLED
        assert world.missions.get_mission(mission.id).status == MissionStatus.CANCELLED
    finally:
        from api.deps import _running_mission_tasks

        _running_mission_tasks.pop(mission.id, None)


def test_second_chat_post_with_the_same_client_message_is_ignored(world, monkeypatch):
    calls: list[str | None] = []

    async def fake_stream(instruction, thread_id, **kwargs):
        calls.append(kwargs.get("client_message_id"))
        run_id = kwargs["run_id"]
        world.runs.create_run(
            instruction=instruction,
            thread_id=thread_id,
            conversation_id=thread_id,
            user_id=kwargs.get("user_id"),
            organization_id=kwargs.get("organization_id"),
            client_message_id=kwargs.get("client_message_id"),
            mission_id=run_id,
            run_id=run_id,
        )
        world.runs.update_status(run_id, RunStatus.RUNNING)
        on_event = kwargs.get("on_event")
        if on_event:
            await on_event({"event": "done", "thread_id": thread_id, "run_id": run_id})
        yield 'data: {"event":"done"}\n\n'

    monkeypatch.setattr(chat, "stream_mission_graph", fake_stream)
    body = {
        "text": "Hello from Ada",
        "conversation_id": "conv-ada",
        "client_message_id": "client-1",
    }
    first = world.client.post("/chat/stream", json=body, headers=_as(world.ada.id))
    second = world.client.post("/chat/stream", json=body, headers=_as(world.ada.id))
    assert first.status_code == 200
    assert second.status_code == 200
    assert "duplicate" in second.text
    assert calls == ["client-1"]
    messages = world.conversations.list_messages("conv-ada")
    assert [message.role for message in messages] == ["user"]
    assert len(world.missions.list_missions(limit=10)) == 1


def test_get_run_is_visible_to_organization_members_only(world):
    mission = world.missions.create_mission(
        instruction="Shared",
        thread_id="thread-shared",
        user_id=world.ada.id,
        organization_id=world.ada_org,
    )
    world.runs.create_run(
        instruction="Shared",
        thread_id="thread-shared",
        conversation_id="thread-shared",
        user_id=world.ada.id,
        organization_id=world.ada_org,
        mission_id=mission.id,
        run_id=mission.id,
    )
    world.runs.append_step(mission.id, kind="tool_call", text="Ada's private step")
    world.board.create_task(
        run_id=mission.id,
        title="Look",
        instruction="Find the note",
        assignee_role="researcher",
    )

    member = world.client.get(f"/runs/{mission.id}", headers=_as(world.grace.id))
    assert member.status_code == 200
    body = member.json()
    assert body["run"]["id"] == mission.id
    assert body["steps"][0]["text"] == "Ada's private step"
    assert body["board_tasks"][0]["title"] == "Look"

    outsider = world.client.get(f"/runs/{mission.id}", headers=_as(world.bea.id))
    assert outsider.status_code == 404
    assert "Ada's private step" not in outsider.text
