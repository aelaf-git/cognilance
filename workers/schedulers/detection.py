"""Open organization alerts from work tasks and organization events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.broker.store import IntegrationStore
from core.context.orgs.store import OrganizationEvent, OrgStore
from core.context.projects.store import WorkTask, is_overdue
from core.context.projects.store import ProjectStore

_STALE_ISSUE_DAYS = 7


def detect_alerts(*, stale_issue_days: int = _STALE_ISSUE_DAYS, now: datetime | None = None) -> int:
    """Open alerts for overdue tasks, quiet selected issues, and done tasks with an open pull request."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    projects = ProjectStore()
    orgs = OrgStore()
    tasks = projects.list_all_tasks()
    events = orgs.list_all_events()
    by_org: dict[str, list[OrganizationEvent]] = {}
    for event in events:
        by_org.setdefault(event.organization_id, []).append(event)
    org_ids = {task.organization_id for task in tasks} | set(by_org)
    opened = 0
    for organization_id in org_ids:
        org_events = by_org.get(organization_id, [])
        org_tasks = [task for task in tasks if task.organization_id == organization_id]
        opened += _overdue_alerts(orgs, organization_id, org_tasks, org_events, moment)
        opened += _stale_issue_alerts(
            orgs, organization_id, org_events, stale_issue_days, moment
        )
        opened += _done_open_pull_request_alerts(orgs, organization_id, org_tasks, org_events)
    return opened


def _overdue_alerts(
    orgs: OrgStore,
    organization_id: str,
    tasks: list[WorkTask],
    events: list[OrganizationEvent],
    now: datetime,
) -> int:
    opened = 0
    for task in tasks:
        if not is_overdue(task, now):
            continue
        event_ids = [
            event.id
            for event in events
            if event.type == "task.deadline_crossed" and event.source_id == task.id
        ]
        alert = orgs.open_alert(
            organization_id,
            f"Work task is past its deadline: {task.title}",
            kind="task.overdue",
            source_key=f"task:{task.id}:overdue",
            fingerprint=str(task.deadline or ""),
            payload={
                "task_id": task.id,
                "event_ids": event_ids,
                "row_ids": [task.id],
            },
            event_ids=event_ids,
            priority=task.priority,
            assignee_account_id=_member_assignee(orgs, organization_id, task.assignee_account_id),
            link={"type": "task", "task_id": task.id, "project_id": task.project_id},
        )
        if alert is not None:
            opened += 1
    return opened


def _selected_repo_ids(organization_id: str) -> set[str]:
    store = IntegrationStore()
    store.init_db()
    grant = store.get_org_grant(organization_id, "github")
    if grant is None:
        return set()
    return {str(repo_id) for repo_id in grant.selected_repos}


def _stale_issue_alerts(
    orgs: OrgStore,
    organization_id: str,
    events: list[OrganizationEvent],
    stale_issue_days: int,
    now: datetime,
) -> int:
    selected = _selected_repo_ids(organization_id)
    if not selected:
        return 0
    cutoff = now - timedelta(days=max(1, int(stale_issue_days)))
    opened = 0
    for event in events:
        if event.type != "github.issue_seen":
            continue
        repo_id = str(event.payload.get("repo_id") or "")
        if repo_id not in selected:
            continue
        url = str(event.payload.get("url") or event.payload.get("issue_url") or "").strip()
        updated = _parse_time(event.payload.get("updated_at"))
        if not url or updated is None or updated >= cutoff:
            continue
        alert = orgs.open_alert(
            organization_id,
            f"Selected repository issue has had no update: {url}",
            kind="github.stale_issue",
            source_key=f"github.stale_issue:{url}",
            fingerprint=updated.isoformat(),
            payload={
                "url": url,
                "repo_id": repo_id,
                "event_ids": [event.id],
                "row_ids": [event.id],
            },
            event_ids=[event.id],
            priority="normal",
            link={"type": "url", "url": url},
        )
        if alert is not None:
            opened += 1
    return opened


def _done_open_pull_request_alerts(
    orgs: OrgStore,
    organization_id: str,
    tasks: list[WorkTask],
    events: list[OrganizationEvent],
) -> int:
    opened_urls = _pull_request_urls(events, "github.pull_request_opened")
    merged_urls = _pull_request_urls(events, "github.pull_request_merged")
    opened = 0
    for task in tasks:
        if task.status != "done":
            continue
        urls = _task_pull_request_urls(task.id, events)
        for url in urls:
            if url not in opened_urls or url in merged_urls:
                continue
            used = [
                event.id
                for event in events
                if event.source_id == task.id or _event_url(event) == url
            ]
            alert = orgs.open_alert(
                organization_id,
                f"Work task is done while its pull request is still open: {url}",
                kind="task.done_open_pr",
                source_key=f"task:{task.id}:open_pr:{url}",
                fingerprint=f"open:{url}",
                payload={
                    "task_id": task.id,
                    "url": url,
                    "event_ids": used,
                    "row_ids": [task.id],
                },
                event_ids=used,
                link={"type": "url", "url": url, "task_id": task.id},
            )
            if alert is not None:
                opened += 1
    return opened


def _member_assignee(orgs: OrgStore, organization_id: str, account_id: str | None) -> str | None:
    account = str(account_id or "").strip()
    if not account or orgs.membership_for(account, organization_id) is None:
        return None
    return account


def _task_pull_request_urls(task_id: str, events: list[OrganizationEvent]) -> list[str]:
    urls: list[str] = []
    for event in events:
        if event.source_id != task_id:
            continue
        url = str(event.payload.get("pull_request_url") or "").strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def _pull_request_urls(events: list[OrganizationEvent], event_type: str) -> set[str]:
    return {url for event in events if event.type == event_type and (url := _event_url(event))}


def _event_url(event: OrganizationEvent) -> str:
    return str(event.payload.get("url") or event.payload.get("pull_request_url") or "").strip()


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
