"""Conversation members share one live stream. Outsiders cannot subscribe."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.routes import chat
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.accounts import AccountStore
from core.runtime.event_bus import event_bus
from core.runtime.missions.models import MissionStatus
from core.runtime.missions.store import MissionStore


def _as(user_id: str) -> dict[str, str]:
    return {"x-user-id": user_id}


def _events_from(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        if not line.startswith("data:"):
            continue
        events.append(json.loads(line.split(":", 1)[1].strip()))
    return events


def _app(conv_store, mission_store, sub_store) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def identify(request: Request, call_next):
        request.state.user_id = request.headers.get("x-user-id") or ""
        return await call_next(request)

    app.include_router(chat.router)
    return app


@pytest.fixture
def world(tmp_path, monkeypatch):
    db = str(tmp_path / "coordinator.db")
    accounts = AccountStore(db)
    orgs = OrgStore(db)
    conv_store = ConversationStore(db)
    mission_store = MissionStore(db)
    sub_store = SubscriptionStore(db)
    for store in (accounts, orgs, conv_store, mission_store, sub_store):
        store.init_db()

    grace = accounts.create(
        email="grace@example.com", password="password1", display_name="Grace"
    )
    ada = accounts.create(email="ada@example.com", password="password1", display_name="Ada")
    outsider = accounts.create(
        email="out@example.com", password="password1", display_name="Outsider"
    )
    shared = orgs.active_for_account(ada.id)
    personal = orgs.active_for_account(grace.id)
    assert shared and personal and shared != personal
    orgs.add_membership(shared, grace.id, "member")

    monkeypatch.setattr("api.deps.account_store", accounts)
    monkeypatch.setattr("api.deps.org_store", orgs)
    monkeypatch.setattr(chat, "conv_store", conv_store)
    monkeypatch.setattr(chat, "mission_store", mission_store)
    monkeypatch.setattr(chat, "sub_store", sub_store)

    conversation = conv_store.create_conversation(
        title="Shared thread",
        user_id=ada.id,
        organization_id=shared,
    )
    older = conv_store.append_message(
        conversation.id, role="user", content="Older note", author_id=ada.id
    )
    kept = conv_store.append_message(
        conversation.id, role="user", content="Kept note", author_id=ada.id
    )
    old_notice = sub_store.append_notification(
        conversation.id,
        subscription_id="sub-old",
        integration="gmail",
        kind="new_email",
        summary="Old notice",
    )
    new_notice = sub_store.append_notification(
        conversation.id,
        subscription_id="sub-new",
        integration="gmail",
        kind="new_email",
        summary="New notice",
    )
    mission = mission_store.create_mission(
        instruction="Keep going",
        conversation_id=conversation.id,
        thread_id=conversation.id,
        user_id=ada.id,
        organization_id=shared,
    )
    mission_store.update_status(mission.id, MissionStatus.RUNNING)
    mission_store.append_event(mission.id, {"event": "status", "message": "Already working"})

    app = _app(conv_store, mission_store, sub_store)
    return SimpleNamespace(
        app=app,
        ada=ada,
        grace=grace,
        outsider=outsider,
        conversation=conversation,
        conv_store=conv_store,
        older=older,
        kept=kept,
        old_notice=old_notice,
        new_notice=new_notice,
        personal=personal,
        orgs=orgs,
    )


def test_outsider_cannot_subscribe(world):
    with TestClient(world.app) as client:
        denied = client.get(
            "/chat/stream",
            params={"conversation_id": world.conversation.id},
            headers=_as(world.outsider.id),
        )
    assert denied.status_code == 404


def test_regenerate_keeps_one_user_message(world, monkeypatch):
    published: list[tuple[str, dict]] = []
    original = event_bus.publish

    async def spy(key, event):
        published.append((key, dict(event)))
        await original(key, event)

    monkeypatch.setattr(event_bus, "publish", spy)

    async def fake_stream(*_args, **kwargs):
        await kwargs["on_event"]({"event": "final", "text": "Rewritten"})
        yield "data: {}\n\n"

    monkeypatch.setattr(chat, "stream_mission_graph", fake_stream)
    before = world.conv_store.list_messages(world.conversation.id, limit=20)
    assistant = world.conv_store.append_message(
        world.conversation.id, role="assistant", content="Old answer"
    )

    with TestClient(world.app) as client:
        response = client.post(
            "/chat/stream",
            json={
                "text": "Kept note",
                "conversation_id": world.conversation.id,
                "regenerate": True,
            },
            headers=_as(world.ada.id),
        )
    assert response.status_code == 200
    stored = world.conv_store.list_messages(world.conversation.id, limit=20)
    assert [item.content for item in stored] == ["Older note", "Kept note", "Rewritten"]
    assert assistant not in {item.id for item in stored}
    assert before[0].content == "Older note"
    removed = [event for _key, event in published if event.get("event") == "message_removed"]
    assert [event["id"] for event in removed] == [assistant]
    user_messages = [
        event
        for key, event in published
        if key == world.conversation.id and event.get("event") == "message" and event.get("role") == "user"
    ]
    assert user_messages == []


def test_members_resume_and_share_live_events(world):
    asyncio.run(_members_share(world))


async def _listen(app: FastAPI, user_id: str, query: bytes, ready: asyncio.Event) -> list[dict]:
    chunks: list[bytes] = []
    disconnected = asyncio.Event()
    sent_body = False

    async def receive():
        nonlocal sent_body
        if not sent_body:
            sent_body = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start" and message["status"] != 200:
            disconnected.set()
            ready.set()
        if message["type"] != "http.response.body":
            return
        body = message.get("body") or b""
        if not body:
            return
        chunks.append(body)
        ready.set()
        if b"live-token" in body:
            disconnected.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/chat/stream",
        "raw_path": b"/chat/stream",
        "query_string": query,
        "headers": [(b"x-user-id", user_id.encode())],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    await app(scope, receive, send)
    text = b"".join(chunks).decode()
    return _events_from(text.splitlines())


async def _members_share(world):
    query = (
        f"conversation_id={world.conversation.id}&after={world.older}"
        f"&after_notification={world.old_notice}"
    ).encode()
    ready_ada = asyncio.Event()
    ready_grace = asyncio.Event()
    ada_task = asyncio.create_task(_listen(world.app, world.ada.id, query, ready_ada))
    grace_task = asyncio.create_task(_listen(world.app, world.grace.id, query, ready_grace))
    try:
        await asyncio.wait_for(asyncio.gather(ready_ada.wait(), ready_grace.wait()), timeout=5)
        await event_bus.close("some-other-mission")
        await event_bus.publish(
            world.conversation.id,
            {
                "event": "message",
                "id": 900,
                "role": "user",
                "content": "From Ada",
                "author_id": world.ada.id,
            },
        )
        await event_bus.publish(
            world.conversation.id,
            {"event": "status", "message": "live-token", "_event_id": 50},
        )
        await event_bus.close(world.conversation.id)
        ada_events, grace_events = await asyncio.wait_for(
            asyncio.gather(ada_task, grace_task), timeout=5
        )
    finally:
        await event_bus.close(world.conversation.id)
        for task in (ada_task, grace_task):
            if not task.done():
                task.cancel()

    for events in (ada_events, grace_events):
        contents = [event.get("content") for event in events if event.get("event") == "message"]
        summaries = [event.get("summary") for event in events if event.get("event") == "notification"]
        statuses = [event.get("message") for event in events if event.get("event") == "status"]
        assert "Older note" not in contents
        assert "Kept note" in contents
        assert "From Ada" in contents
        assert "Old notice" not in summaries
        assert "New notice" in summaries
        assert "Already working" in statuses
        assert "live-token" in statuses
