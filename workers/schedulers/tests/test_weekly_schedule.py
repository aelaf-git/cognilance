"""A Monday 9:00 schedule fires a weekly-report Run and can fire again after a failure."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.subscriptions.models import SubscriptionStatus
from core.context.subscriptions.schedule import create_schedule
from core.context.subscriptions.session_sync import (
    pause_listener_for_mission,
    start_listener_for_mission,
    stop_listener_for_mission,
)
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.accounts import AccountStore
from core.runtime.missions.store import MissionStore
from core.runtime.runs.models import RunStatus, RunTrigger
from core.runtime.runs.store import RunStore
from workers.schedulers.ticker import tick_subscriptions


MONDAY = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)


class _MondayClock(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return MONDAY.replace(tzinfo=None)
        return MONDAY.astimezone(tz)


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", path)
    monkeypatch.setattr("core.context.subscriptions.store.datetime", _MondayClock)
    accounts = AccountStore(path)
    orgs = OrgStore(path)
    missions = MissionStore(path)
    subs = SubscriptionStore(path)
    convs = ConversationStore(path)
    runs = RunStore(path)
    for store in (accounts, orgs, missions, subs, convs, runs):
        store.init_db()
    ada = accounts.create(email="ada@example.com", password="password1", display_name="Ada")
    org_id = orgs.active_for_account(ada.id)
    assert org_id
    convs.create_conversation(title="Launch", user_id=ada.id, organization_id=org_id)
    return path


def _stores(path: str):
    return (
        OrgStore(path),
        SubscriptionStore(path),
        MissionStore(path),
        RunStore(path),
    )


def _message_count(path: str) -> int:
    with sqlite3.connect(path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0])


def _schedule(path: str):
    orgs, subs, missions, _runs = _stores(path)
    ada = AccountStore(path).get_by_email("ada@example.com")
    assert ada is not None
    org_id = orgs.active_for_account(ada.id)
    assert org_id
    created = create_schedule(
        organization_id=org_id,
        user_id=ada.id,
        payload={
            "pipeline": "weekly_report",
            "weekday": "monday",
            "hour": 9,
            "timezone": "UTC",
            "project_id": "proj-1",
        },
        org_store=orgs,
        sub_store=subs,
        mission_store=missions,
        now=MONDAY,
    )
    return created


async def test_monday_nine_creates_a_schedule_run_without_a_chat_message(db, monkeypatch):
    calls: list[str] = []

    async def fake_graph(*, pipeline: str, instruction: str, run_id: str, user_id: str) -> None:
        calls.append(instruction)

    monkeypatch.setattr("workers.schedulers.dispatch.run_pipeline_graph", fake_graph)
    created = _schedule(db)
    assert _message_count(db) == 0

    checked = await tick_subscriptions()
    assert checked == 1
    assert calls == ["Weekly report for project proj-1"]
    assert _message_count(db) == 0

    runs = RunStore(db).list_for_organization(
        OrgStore(db).active_for_account(AccountStore(db).get_by_email("ada@example.com").id)
    )
    assert len(runs) == 1
    assert runs[0].trigger == RunTrigger.SCHEDULE
    assert runs[0].status == RunStatus.COMPLETED
    assert runs[0].conversation_id is None or not runs[0].conversation_id.startswith("conv")

    again = await tick_subscriptions()
    assert again == 0
    assert len(RunStore(db).list_for_organization(runs[0].organization_id)) == 1
    saved = SubscriptionStore(db).get_subscription(created["subscription_id"])
    assert saved is not None
    assert saved.status == SubscriptionStatus.ACTIVE
    assert saved.error is None
    assert saved.next_check_at.astimezone(timezone.utc) == MONDAY.replace(day=23)


async def test_a_failed_fire_stays_due_for_the_next_tick(db, monkeypatch):
    async def boom(*, pipeline: str, instruction: str, run_id: str, user_id: str) -> None:
        raise RuntimeError("report failed")

    monkeypatch.setattr("workers.schedulers.dispatch.run_pipeline_graph", boom)
    created = _schedule(db)
    await tick_subscriptions()

    runs = RunStore(db).list_for_organization(created["organization_id"])
    assert len(runs) == 1
    assert runs[0].status == RunStatus.FAILED
    saved = SubscriptionStore(db).get_subscription(created["subscription_id"])
    assert saved is not None
    assert saved.status == SubscriptionStatus.ACTIVE
    assert saved.error == "report failed"
    assert saved.id in {sub.id for sub in SubscriptionStore(db).list_due()}

    async def fine(*, pipeline: str, instruction: str, run_id: str, user_id: str) -> None:
        return None

    monkeypatch.setattr("workers.schedulers.dispatch.run_pipeline_graph", fine)
    await tick_subscriptions()
    statuses = {
        run.status
        for run in RunStore(db).list_for_organization(created["organization_id"])
    }
    assert statuses == {RunStatus.FAILED, RunStatus.COMPLETED}
    recovered = SubscriptionStore(db).get_subscription(created["subscription_id"])
    assert recovered is not None
    assert recovered.status == SubscriptionStatus.ACTIVE
    assert recovered.error is None


async def test_paused_is_skipped_and_start_makes_a_stopped_schedule_due(db, monkeypatch):
    async def fake_graph(*, pipeline: str, instruction: str, run_id: str, user_id: str) -> None:
        return None

    monkeypatch.setattr("workers.schedulers.dispatch.run_pipeline_graph", fake_graph)
    created = _schedule(db)
    subs = SubscriptionStore(db)
    missions = MissionStore(db)
    assert pause_listener_for_mission(
        created["session_id"], sub_store=subs, mission_store=missions
    )
    assert subs.list_due() == []
    assert await tick_subscriptions() == 0
    assert RunStore(db).list_for_organization(created["organization_id"]) == []

    assert stop_listener_for_mission(
        created["session_id"], sub_store=subs, mission_store=missions
    )
    stopped = subs.get_subscription(created["subscription_id"])
    assert stopped is not None
    assert stopped.status == SubscriptionStatus.STOPPED

    assert start_listener_for_mission(
        created["session_id"], sub_store=subs, mission_store=missions
    )
    due = subs.list_due()
    assert [sub.id for sub in due] == [created["subscription_id"]]
    assert due[0].status == SubscriptionStatus.ACTIVE


def _create(path: str, payload: dict, *, now: datetime = MONDAY) -> dict:
    orgs, subs, missions, _runs = _stores(path)
    ada = AccountStore(path).get_by_email("ada@example.com")
    assert ada is not None
    org_id = orgs.active_for_account(ada.id)
    assert org_id
    return create_schedule(
        organization_id=org_id,
        user_id=ada.id,
        payload=payload,
        org_store=orgs,
        sub_store=subs,
        mission_store=missions,
        now=now,
    )


async def test_daily_and_interval_advance_on_their_own_cadence(db, monkeypatch):
    seen: list[str] = []

    async def fake_graph(*, pipeline: str, instruction: str, run_id: str, user_id: str) -> None:
        seen.append(pipeline)

    monkeypatch.setattr("workers.schedulers.dispatch.run_pipeline_graph", fake_graph)
    daily = _create(
        db,
        {
            "cadence": {"type": "daily", "hour": 9},
            "action": {"type": "pipeline", "pipeline": "email_followup"},
            "timezone": "UTC",
        },
    )
    interval = _create(
        db,
        {
            "cadence": {"type": "interval", "every_seconds": 300},
            "action": {"type": "pipeline", "pipeline": "concept_note"},
            "timezone": "UTC",
        },
        now=MONDAY - timedelta(seconds=300),
    )
    await tick_subscriptions()
    assert set(seen) == {"email_followup", "concept_note"}
    saved_daily = SubscriptionStore(db).get_subscription(daily["subscription_id"])
    saved_interval = SubscriptionStore(db).get_subscription(interval["subscription_id"])
    assert saved_daily is not None and saved_interval is not None
    assert saved_daily.next_check_at.astimezone(timezone.utc) == MONDAY + timedelta(days=1)
    assert saved_interval.next_check_at.astimezone(timezone.utc) == MONDAY + timedelta(seconds=300)


async def test_instruction_and_legacy_weekly_rows_record_a_schedule_run(db, monkeypatch):
    calls: list[str] = []

    async def fake_graph(*, pipeline: str, instruction: str, run_id: str, user_id: str) -> None:
        calls.append(pipeline)

    async def fake_instruction(*, user_id: str, conversation_id: str, instruction: str, mission_id=None):
        assert mission_id is None
        run = RunStore().create_run(
            instruction=instruction,
            thread_id=conversation_id,
            trigger=RunTrigger.SCHEDULE,
            user_id=user_id,
            organization_id=created["organization_id"],
        )
        RunStore().update_status(run.id, RunStatus.COMPLETED, result_text=instruction)
        return {"had_error": False, "run_id": run.id, "text": instruction}

    monkeypatch.setattr("workers.schedulers.dispatch.run_pipeline_graph", fake_graph)
    monkeypatch.setattr("workers.schedulers.dispatch.run_recurring_instruction", fake_instruction)
    created = _create(
        db,
        {
            "cadence": {"type": "weekly", "weekday": "monday", "hour": 9},
            "action": {"type": "instruction", "instruction": "Summarize open tasks"},
            "timezone": "UTC",
        },
    )
    ada = AccountStore(db).get_by_email("ada@example.com")
    assert ada is not None
    org_id = created["organization_id"]
    legacy = SubscriptionStore(db).create_subscription(
        user_id=ada.id,
        conversation_id="",
        integration="schedule",
        kind="weekly_report",
        config={
            "pipeline": "weekly_report",
            "weekday": 0,
            "hour": 9,
            "timezone": "UTC",
            "project_id": "proj-1",
        },
        organization_id=org_id,
        next_check_at=MONDAY,
    )
    assert _message_count(db) == 0
    await tick_subscriptions()
    assert calls == ["weekly_report"]
    assert _message_count(db) == 0
    runs = RunStore(db).list_for_organization(org_id)
    assert {run.trigger for run in runs} == {RunTrigger.SCHEDULE}
    assert {run.instruction for run in runs} == {
        "Summarize open tasks",
        "Weekly report for project proj-1",
    }
    legacy_saved = SubscriptionStore(db).get_subscription(legacy.id)
    assert legacy_saved is not None
    assert legacy_saved.next_check_at.astimezone(timezone.utc) == MONDAY.replace(day=23)
