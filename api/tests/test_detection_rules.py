"""Ticker detection opens alerts and leaves a dismissal in place until the source changes."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.broker.crypto import _fernet
from core.broker.store import IntegrationStore
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.projects.store import ProjectStore
from core.context.subscriptions.store import SubscriptionStore
from workers.schedulers.ticker import tick_subscriptions


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", path)
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")
    _fernet.cache_clear()
    for store in (
        OrgStore(path),
        ProjectStore(path),
        SubscriptionStore(path),
        ConversationStore(path),
        IntegrationStore(path),
    ):
        store.init_db()
    return path


def _message_count(path: str) -> int:
    with sqlite3.connect(path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0])


def _overdue_task(path: str):
    projects = ProjectStore(path)
    project = projects.create_project("org-a", "Launch", created_by="ada")
    deadline = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    return projects.create_task(
        project.id,
        organization_id="org-a",
        title="Ship the brief",
        created_by="ada",
        deadline=deadline,
    )


async def test_one_ticker_pass_opens_one_overdue_alert_without_a_chat_message(db):
    task = _overdue_task(db)
    assert _message_count(db) == 0
    await tick_subscriptions()
    alerts = OrgStore(db).list_alerts("org-a")
    assert len(alerts) == 1
    assert alerts[0].kind == "task.overdue"
    assert alerts[0].payload["task_id"] == task.id
    assert alerts[0].event_ids
    assert _message_count(db) == 0
    await tick_subscriptions()
    assert len(OrgStore(db).list_alerts("org-a")) == 1


async def test_a_dismissed_overdue_alert_stays_dismissed_on_the_next_tick(db):
    _overdue_task(db)
    await tick_subscriptions()
    orgs = OrgStore(db)
    alert = orgs.list_alerts("org-a")[0]
    assert orgs.dismiss_alert(alert.id) is True
    await tick_subscriptions()
    alerts = orgs.list_alerts("org-a")
    assert len(alerts) == 1
    assert alerts[0].id == alert.id
    assert alerts[0].dismissed_at is not None


def _select_repo(path: str, organization_id: str, repo_ids: list[str]) -> None:
    grants = IntegrationStore(path)
    grants.save_org_grant(
        organization_id=organization_id,
        integration="github",
        access_token="ghp_test_secret",
        refresh_token=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    grants.set_selected_repos(organization_id, "github", repo_ids)


def _issue(organization_id: str, delivery_id: str, repo_id: str, number: int) -> dict:
    updated = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    return {
        "organization_id": organization_id,
        "delivery_id": delivery_id,
        "action": "issue",
        "payload": {
            "repo_id": repo_id,
            "url": f"https://github.com/acme/app/issues/{number}",
            "updated_at": updated,
        },
    }


async def test_a_quiet_selected_issue_alerts_once_and_an_unselected_repo_does_not(db):
    _select_repo(db, "org-a", ["101"])
    selected = _issue("org-a", "issue-1", "101", 3)
    await tick_subscriptions(github_deliveries=[selected])
    alerts = OrgStore(db).list_alerts("org-a")
    assert len(alerts) == 1
    assert alerts[0].payload["url"] == "https://github.com/acme/app/issues/3"
    await tick_subscriptions(github_deliveries=[selected, _issue("org-a", "issue-2", "999", 9)])
    alerts = OrgStore(db).list_alerts("org-a")
    assert len(alerts) == 1
    assert alerts[0].payload["url"] == "https://github.com/acme/app/issues/3"


async def test_a_done_task_with_an_open_pull_request_alerts_until_that_pull_request_merges(db):
    projects = ProjectStore(db)
    orgs = OrgStore(db)
    project = projects.create_project("org-a", "Launch", created_by="ada")
    task = projects.create_task(
        project.id,
        organization_id="org-a",
        title="Ship the brief",
        created_by="ada",
        status="done",
    )
    url = "https://github.com/acme/app/pull/7"
    orgs.record_event(
        "org-a",
        "task.updated",
        source_id=task.id,
        payload={"pull_request_url": url},
        idempotency_key=f"task:{task.id}:pr",
    )
    opened = {
        "organization_id": "org-a",
        "delivery_id": "delivery-pr",
        "action": "opened",
        "payload": {"url": url},
    }
    await tick_subscriptions(github_deliveries=[opened])
    alerts = orgs.list_alerts("org-a")
    assert len(alerts) == 1
    assert alerts[0].kind == "task.done_open_pr"
    assert alerts[0].payload["task_id"] == task.id
    assert alerts[0].payload["url"] == url
    assert alerts[0].fingerprint == f"open:{url}"

    merged = {
        "organization_id": "org-a",
        "delivery_id": "delivery-pr",
        "action": "merged",
        "payload": {"url": url},
    }
    await tick_subscriptions(github_deliveries=[merged])
    later = orgs.list_alerts("org-a")
    assert len(later) == 1
    assert later[0].id == alerts[0].id
    assert later[0].fingerprint == f"open:{url}"
