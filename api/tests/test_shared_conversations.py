"""A conversation is shared with every membership of its organization."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.routes import conversations
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.accounts import AccountStore
from core.runtime.missions.store import MissionStore


class _EmptyDrafts:
    def get_active_doc(self, conversation_id: str):
        return None


def _as(user_id: str) -> dict[str, str]:
    return {"x-user-id": user_id}


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
    monkeypatch.setattr(conversations, "conv_store", conv_store)
    monkeypatch.setattr(conversations, "mission_store", mission_store)
    monkeypatch.setattr(conversations, "sub_store", sub_store)
    monkeypatch.setattr(conversations, "DraftStore", _EmptyDrafts)
    monkeypatch.setattr(conversations, "active_document_id", lambda _conversation_id: None)

    conversation = conv_store.create_conversation(
        title="Shared thread",
        user_id=ada.id,
        organization_id=shared,
    )
    conv_store.append_message(
        conversation.id, role="user", content="Hello from Ada", author_id=ada.id
    )
    conv_store.append_message(conversation.id, role="assistant", content="Hello Ada")
    conv_store.append_message(
        conversation.id, role="user", content="Hello from Grace", author_id=grace.id
    )

    app = FastAPI()

    @app.middleware("http")
    async def identify(request: Request, call_next):
        request.state.user_id = request.headers.get("x-user-id") or ""
        return await call_next(request)

    app.include_router(conversations.router)

    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            db=db,
            ada=ada,
            grace=grace,
            outsider=outsider,
            shared=shared,
            personal=personal,
            conversation=conversation,
            orgs=orgs,
        )


def test_members_see_the_same_messages_and_an_outsider_is_not_found(world):
    client = world.client
    assert world.orgs.active_for_account(world.grace.id) == world.personal

    ada_view = client.get(f"/conversations/{world.conversation.id}", headers=_as(world.ada.id))
    grace_view = client.get(
        f"/conversations/{world.conversation.id}", headers=_as(world.grace.id)
    )
    assert ada_view.status_code == 200
    assert grace_view.status_code == 200
    ada_messages = ada_view.json()["messages"]
    grace_messages = grace_view.json()["messages"]
    assert [item["id"] for item in ada_messages] == [item["id"] for item in grace_messages]
    assert [item["content"] for item in grace_messages] == [
        "Hello from Ada",
        "Hello Ada",
        "Hello from Grace",
    ]
    assert grace_messages[0]["author_id"] == world.ada.id
    assert grace_messages[0]["author_name"] == "Ada"
    assert grace_messages[1]["author_id"] is None
    assert grace_messages[1]["author_name"] == "Cognilance"
    assert grace_messages[2]["author_id"] == world.grace.id
    assert grace_messages[2]["author_name"] == "Grace"

    listed = client.get("/conversations", headers=_as(world.grace.id))
    assert listed.status_code == 200
    assert world.conversation.id in {item["id"] for item in listed.json()["conversations"]}

    hidden = client.get(f"/conversations/{world.conversation.id}", headers=_as(world.outsider.id))
    assert hidden.status_code == 404
    outsider_list = client.get("/conversations", headers=_as(world.outsider.id))
    assert world.conversation.id not in {
        item["id"] for item in outsider_list.json()["conversations"]
    }


def test_before_returns_older_messages_and_history_survives_reopen(world):
    client = world.client
    current = client.get(f"/conversations/{world.conversation.id}", headers=_as(world.ada.id))
    messages = current.json()["messages"]
    newest = messages[-1]["id"]

    older = client.get(
        f"/conversations/{world.conversation.id}",
        params={"before": newest},
        headers=_as(world.ada.id),
    )
    assert older.status_code == 200
    assert [item["id"] for item in older.json()["messages"]] == [item["id"] for item in messages[:-1]]
    assert all(item["id"] < newest for item in older.json()["messages"])

    reopened = ConversationStore(world.db)
    stored = reopened.list_messages(world.conversation.id)
    assert [item.content for item in stored] == [item["content"] for item in messages]
    assert stored[0].author_id == world.ada.id
    assert stored[1].author_id is None
