"""Organization events are written once and stay inside the organization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.context.orgs.store import OrgStore
from core.context.projects.store import ProjectStore
from core.context.subscriptions.store import SubscriptionStore
from core.runtime.runs.models import RunStatus
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.loop import _record_approval_rejected
from workers.schedulers.github_events import note_github_delivery
from workers.schedulers.ticker import tick_subscriptions


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", path)
    for store in (OrgStore(path), ProjectStore(path), RunStore(path), SubscriptionStore(path)):
        store.init_db()
    return path


def test_creating_a_work_task_inserts_one_event_for_that_organization(db):
    projects = ProjectStore(db)
    orgs = OrgStore(db)
    project = projects.create_project("org-a", "Launch", created_by="ada")
    task = projects.create_task(
        project.id,
        organization_id="org-a",
        title="Write the brief",
        created_by="ada",
    )
    events = orgs.list_events("org-a")
    assert len(events) == 1
    assert events[0].type == "task.created"
    assert events[0].source_id == task.id
    assert events[0].payload["title"] == "Write the brief"
    assert orgs.list_events("org-b") == []


def test_replaying_a_github_delivery_does_not_insert_a_second_event(db):
    orgs = OrgStore(db)
    payload = {"number": 7, "url": "https://github.com/acme/app/pull/7"}
    assert note_github_delivery("org-a", "delivery-1", "opened", payload) is True
    assert note_github_delivery("org-a", "delivery-1", "opened", payload) is False
    events = orgs.list_events("org-a")
    assert len(events) == 1
    assert events[0].type == "github.pull_request_opened"
    assert events[0].idempotency_key == "github:delivery-1:opened"

    assert (
        note_github_delivery("org-a", "delivery-1", "merged", {"number": 7}) is True
    )
    assert [event.type for event in orgs.list_events("org-a")] == [
        "github.pull_request_opened",
        "github.pull_request_merged",
    ]


def test_events_for_one_organization_are_invisible_to_another(db):
    projects = ProjectStore(db)
    orgs = OrgStore(db)
    own = projects.create_project("org-a", "Launch", created_by="ada")
    other = projects.create_project("org-b", "Other", created_by="bea")
    projects.create_task(own.id, organization_id="org-a", title="Ours", created_by="ada")
    projects.create_task(other.id, organization_id="org-b", title="Theirs", created_by="bea")
    visible = orgs.list_events("org-a")
    assert [event.payload["title"] for event in visible] == ["Ours"]
    assert all(event.organization_id == "org-a" for event in visible)
    assert [event.payload["title"] for event in orgs.list_events("org-b")] == ["Theirs"]


def test_deadline_run_and_rejection_events_are_written_once(db):
    projects = ProjectStore(db)
    orgs = OrgStore(db)
    runs = RunStore(db)
    project = projects.create_project("org-a", "Launch", created_by="ada")
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    task = projects.create_task(
        project.id,
        organization_id="org-a",
        title="Ship it",
        created_by="ada",
        deadline=past,
    )
    projects.update_task(task.id, organization_id="org-a", actor_id="ada", status="in_progress")

    assert projects.note_deadline_crossings() == 1
    assert projects.note_deadline_crossings() == 0

    run = runs.create_run(
        instruction="Weekly report",
        thread_id="schedule:1",
        organization_id="org-a",
        user_id="ada",
    )
    runs.update_status(run.id, RunStatus.COMPLETED, result_text="done")
    runs.update_status(run.id, RunStatus.COMPLETED, result_text="done")

    _record_approval_rejected({"run_id": run.id})
    _record_approval_rejected({"run_id": run.id})

    kinds = [event.type for event in orgs.list_events("org-a")]
    assert kinds == [
        "task.created",
        "task.updated",
        "task.deadline_crossed",
        "run.completed",
        "approval.rejected",
    ]


async def test_a_second_deadline_tick_does_not_insert_another_event(db):
    projects = ProjectStore(db)
    orgs = OrgStore(db)
    project = projects.create_project("org-a", "Launch", created_by="ada")
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    projects.create_task(
        project.id,
        organization_id="org-a",
        title="Ship it",
        created_by="ada",
        deadline=past,
    )
    await tick_subscriptions()
    await tick_subscriptions()
    crossed = [event for event in orgs.list_events("org-a") if event.type == "task.deadline_crossed"]
    assert len(crossed) == 1
