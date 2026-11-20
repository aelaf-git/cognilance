"""Plan context stays inside one organization and within the prompt budget."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from langchain_core.messages import HumanMessage

from agents.coordinator.schema import PlannedTask, Result
from core.context.conversations.store import ConversationMessage, ConversationStore
from core.context.orgs.store import OrganizationNote, OrgStore
from core.context.projects.store import ProjectStore, WorkTask, WorkTaskActivity
from core.context.request import current_conversation_id
from core.runtime.missions.store import MissionStore
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.coordinator import coordinator_plan
from pipelines.coordinator_board.org_context import CONTEXT_BUDGET, organization_context, resolve_source


class _Capture:
    def __init__(self) -> None:
        self.prompt = ""

    async def ainvoke(self, prompt: str) -> Result:
        self.prompt = prompt
        return Result(
            reasoning="ok",
            tasks=[PlannedTask(title="Reply", instruction="Say hello", assignee_role="researcher")],
        )


def _decision(db: str, task_id: str, text: str) -> str:
    activity_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO work_task_activity (id, task_id, actor_id, action, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (activity_id, task_id, "ada", "decision", json.dumps({"text": text}), now),
        )
    return activity_id


@pytest.fixture
def world(tmp_path, monkeypatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    projects = ProjectStore(db)
    orgs = OrgStore(db)
    conversations = ConversationStore(db)
    runs = RunStore(db)
    for store in (projects, orgs, conversations, runs, MissionStore(db)):
        store.init_db()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    ours = projects.create_project("org-a", "Launch pad", created_by="ada")
    theirs = projects.create_project("org-b", "Launch pad", created_by="bea")
    open_task = projects.create_task(
        ours.id,
        organization_id="org-a",
        title="File the brief",
        created_by="ada",
        deadline=past,
        status="open",
    )
    done = projects.create_task(
        ours.id,
        organization_id="org-a",
        title="Already finished",
        created_by="ada",
        status="done",
    )
    hidden = projects.create_task(
        theirs.id,
        organization_id="org-b",
        title="Other org secret",
        created_by="bea",
        status="open",
    )
    decision = _decision(db, open_task.id, "Ship on Friday")
    hidden_decision = _decision(db, hidden.id, "Secret decision")
    note = orgs.add_note("org-a", "Prefer short bullets")
    hidden_note = orgs.add_note("org-b", "Secret preference")
    conversation = conversations.create_conversation(
        title="Weekly", organization_id="org-a", user_id="ada"
    )
    message_id = conversations.append_message(
        conversation.id, role="user", content="See you Monday"
    )
    run = runs.create_run(
        instruction="Plan the work",
        thread_id=conversation.id,
        conversation_id=conversation.id,
        organization_id="org-a",
        user_id="ada",
        run_id="run-a",
    )
    return {
        "db": db,
        "run": run,
        "conversation": conversation,
        "open_task": open_task,
        "done": done,
        "hidden": hidden,
        "decision": decision,
        "hidden_decision": hidden_decision,
        "note": note,
        "hidden_note": hidden_note,
        "message_id": message_id,
    }


def _state(world, text: str) -> dict:
    return {
        "run_id": world["run"].id,
        "messages": [HumanMessage(content=text)],
    }


def test_named_project_uses_only_that_organization(world):
    token = current_conversation_id.set(world["conversation"].id)
    try:
        context = organization_context(_state(world, "How is Launch pad going?"), "How is Launch pad going?")
    finally:
        current_conversation_id.reset(token)

    assert f"[source:{world['open_task'].id}]" in context
    assert f"[source:{world['decision']}]" in context
    assert f"[source:{world['note'].id}]" in context
    assert f"[source:{world['message_id']}]" in context
    assert "File the brief" in context
    assert "Ship on Friday" in context
    assert "Prefer short bullets" in context
    assert "Already finished" not in context
    assert world["hidden"].id not in context
    assert "Other org secret" not in context
    assert world["hidden_decision"] not in context
    assert "Secret decision" not in context
    assert world["hidden_note"].id not in context
    assert "Secret preference" not in context

    task = resolve_source("org-a", world["open_task"].id)
    activity = resolve_source("org-a", world["decision"])
    message = resolve_source("org-a", str(world["message_id"]))
    note = resolve_source("org-a", world["note"].id)
    assert isinstance(task, WorkTask)
    assert task.title == "File the brief"
    assert isinstance(activity, WorkTaskActivity)
    assert activity.action == "decision"
    assert isinstance(message, ConversationMessage)
    assert message.content == "See you Monday"
    assert isinstance(note, OrganizationNote)
    assert resolve_source("org-a", world["hidden"].id) is None
    assert resolve_source("org-a", world["hidden_decision"]) is None
    assert resolve_source("org-a", world["hidden_note"].id) is None


@pytest.mark.asyncio
async def test_unnamed_project_keeps_history_and_still_plans(world, monkeypatch):
    token = current_conversation_id.set(world["conversation"].id)
    capture = _Capture()
    monkeypatch.setattr(
        "pipelines.coordinator_board.coordinator.get_structured_llm",
        lambda *_args, **_kwargs: capture,
    )
    try:
        plan = await coordinator_plan(_state(world, "What should I do today?"))
    finally:
        current_conversation_id.reset(token)

    assert plan["plan"]["steps"]
    assert "See you Monday" in capture.prompt
    assert f"[source:{world['message_id']}]" in capture.prompt
    assert "File the brief" not in capture.prompt
    assert "Ship on Friday" not in capture.prompt
    assert "Prefer short bullets" not in capture.prompt
    assert "Already finished" not in capture.prompt


def test_long_history_stays_within_the_budget(world):
    conversations = ConversationStore(world["db"])
    oldest = "OLDEST-TOKEN " + ("x" * 800)
    newest = "NEWEST-TOKEN " + ("y" * 800)
    conversations.append_message(world["conversation"].id, role="user", content=oldest)
    for index in range(12):
        conversations.append_message(
            world["conversation"].id,
            role="user",
            content=f"filler {index} " + ("z" * 800),
        )
    conversations.append_message(world["conversation"].id, role="user", content=newest)
    token = current_conversation_id.set(world["conversation"].id)
    try:
        context = organization_context(_state(world, "hello"), "hello")
    finally:
        current_conversation_id.reset(token)

    assert len(context) <= CONTEXT_BUDGET
    assert "NEWEST-TOKEN" in context
    assert "OLDEST-TOKEN" not in context
    assert "y" * 800 not in context
