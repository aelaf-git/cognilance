"""SQLite projects and work tasks, separate from per-run board tasks."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.context.db import ensure_db_dir

STATUSES = ("open", "in_progress", "blocked", "done")
PRIORITIES = ("low", "normal", "high")
_UNSET = object()


@dataclass
class Project:
    id: str
    organization_id: str
    title: str
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass
class WorkTask:
    id: str
    project_id: str
    organization_id: str
    title: str
    status: str
    priority: str
    deadline: str | None
    assignee_account_id: str | None
    assignee_agent_id: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


@dataclass
class WorkTaskComment:
    id: str
    task_id: str
    author_id: str
    body: str
    created_at: datetime


@dataclass
class WorkTaskActivity:
    id: str
    task_id: str
    actor_id: str
    action: str
    payload: dict[str, Any]
    created_at: datetime


class ProjectStore:
    def __init__(self, db_path: str | None = None) -> None:
        self._path = str(db_path or ensure_db_dir())

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_projects_org
                    ON projects(organization_id);
                CREATE TABLE IF NOT EXISTS work_tasks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    deadline TEXT,
                    assignee_account_id TEXT,
                    assignee_agent_id TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_work_tasks_project
                    ON work_tasks(project_id);
                CREATE TABLE IF NOT EXISTS work_task_comments (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_work_task_comments_task
                    ON work_task_comments(task_id);
                CREATE TABLE IF NOT EXISTS work_task_activity (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_work_task_activity_task
                    ON work_task_activity(task_id);
                """
            )

    def create_project(self, organization_id: str, title: str, *, created_by: str) -> Project:
        cleaned = _title(title)
        now = _now()
        project_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO projects (
                    id, organization_id, title, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project_id, organization_id, cleaned, created_by, now, now),
            )
        project = self.get_project(project_id, organization_id=organization_id)
        assert project is not None
        return project

    def list_projects(self, organization_id: str) -> list[Project]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM projects
                WHERE organization_id = ?
                ORDER BY created_at ASC
                """,
                (organization_id,),
            ).fetchall()
        return [_project_from_row(row) for row in rows]

    def search_projects(self, organization_id: str, *, query: str = "") -> list[Project]:
        needle = query.strip().lower()
        projects = self.list_projects(organization_id)
        if not needle:
            return projects
        return [item for item in projects if needle in item.title.lower()]

    def get_project(self, project_id: str, *, organization_id: str | None = None) -> Project | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        project = _project_from_row(row)
        if organization_id and project.organization_id != organization_id:
            return None
        return project

    def update_project(
        self, project_id: str, *, organization_id: str, title: str
    ) -> Project | None:
        if self.get_project(project_id, organization_id=organization_id) is None:
            return None
        cleaned = _title(title)
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE projects SET title = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?
                """,
                (cleaned, _now(), project_id, organization_id),
            )
        return self.get_project(project_id, organization_id=organization_id)

    def delete_project(self, project_id: str, *, organization_id: str) -> bool:
        if self.get_project(project_id, organization_id=organization_id) is None:
            return False
        with self._conn() as conn:
            task_ids = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM work_tasks WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            ]
            for task_id in task_ids:
                conn.execute("DELETE FROM work_task_comments WHERE task_id = ?", (task_id,))
                conn.execute("DELETE FROM work_task_activity WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM work_tasks WHERE project_id = ?", (project_id,))
            conn.execute(
                "DELETE FROM projects WHERE id = ? AND organization_id = ?",
                (project_id, organization_id),
            )
        return True

    def create_task(
        self,
        project_id: str,
        *,
        organization_id: str,
        title: str,
        created_by: str,
        status: str = "open",
        priority: str = "normal",
        deadline: str | None = None,
        assignee_account_id: str | None = None,
        assignee_agent_id: str | None = None,
    ) -> WorkTask:
        if self.get_project(project_id, organization_id=organization_id) is None:
            raise ValueError("Project not found")
        cleaned_status = _choice(status or "open", STATUSES, "status")
        cleaned_priority = _choice(priority or "normal", PRIORITIES, "priority")
        cleaned_deadline = _deadline(deadline)
        account_id, agent_id = _assignees(assignee_account_id, assignee_agent_id)
        now = _now()
        task_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO work_tasks (
                    id, project_id, organization_id, title, status, priority, deadline,
                    assignee_account_id, assignee_agent_id, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    project_id,
                    organization_id,
                    _title(title),
                    cleaned_status,
                    cleaned_priority,
                    cleaned_deadline,
                    account_id,
                    agent_id,
                    created_by,
                    now,
                    now,
                ),
            )
            _insert_activity(
                conn,
                task_id,
                created_by,
                "created",
                {"title": _title(title), "status": cleaned_status},
                now,
            )
        task = self.get_task(task_id, organization_id=organization_id)
        assert task is not None
        return task

    def list_tasks(self, project_id: str, *, organization_id: str) -> list[WorkTask]:
        if self.get_project(project_id, organization_id=organization_id) is None:
            raise ValueError("Project not found")
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM work_tasks
                WHERE project_id = ? AND organization_id = ?
                ORDER BY created_at ASC
                """,
                (project_id, organization_id),
            ).fetchall()
        return [_task_from_row(row) for row in rows]

    def search_tasks(
        self,
        organization_id: str,
        *,
        query: str = "",
        status: str | None = None,
        overdue: bool = False,
        now: datetime | None = None,
    ) -> list[WorkTask]:
        if not organization_id:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM work_tasks
                WHERE organization_id = ?
                ORDER BY created_at ASC
                """,
                (organization_id,),
            ).fetchall()
        tasks = [_task_from_row(row) for row in rows]
        needle = query.strip().lower()
        if needle:
            tasks = [item for item in tasks if needle in item.title.lower()]
        if status:
            cleaned = _choice(str(status), STATUSES, "status")
            tasks = [item for item in tasks if item.status == cleaned]
        if overdue:
            moment = now or datetime.now(timezone.utc)
            tasks = [item for item in tasks if is_overdue(item, moment)]
        return tasks

    def get_task(self, task_id: str, *, organization_id: str | None = None) -> WorkTask | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM work_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        task = _task_from_row(row)
        if organization_id and task.organization_id != organization_id:
            return None
        return task

    def update_task(
        self,
        task_id: str,
        *,
        organization_id: str,
        actor_id: str,
        title: Any = _UNSET,
        status: Any = _UNSET,
        priority: Any = _UNSET,
        deadline: Any = _UNSET,
        assignee_account_id: Any = _UNSET,
        assignee_agent_id: Any = _UNSET,
    ) -> WorkTask | None:
        current = self.get_task(task_id, organization_id=organization_id)
        if current is None:
            return None
        changes: dict[str, Any] = {}
        next_title = current.title
        next_status = current.status
        next_priority = current.priority
        next_deadline = current.deadline
        next_account = current.assignee_account_id
        next_agent = current.assignee_agent_id
        if title is not _UNSET:
            next_title = _title(str(title or ""))
            if next_title != current.title:
                changes["title"] = next_title
        if status is not _UNSET:
            next_status = _choice(str(status or ""), STATUSES, "status")
            if next_status != current.status:
                changes["status"] = next_status
        if priority is not _UNSET:
            next_priority = _choice(str(priority or ""), PRIORITIES, "priority")
            if next_priority != current.priority:
                changes["priority"] = next_priority
        if deadline is not _UNSET:
            next_deadline = _deadline(None if deadline is None else str(deadline))
            if next_deadline != current.deadline:
                changes["deadline"] = next_deadline
        if assignee_account_id is not _UNSET or assignee_agent_id is not _UNSET:
            account_value = (
                current.assignee_account_id
                if assignee_account_id is _UNSET
                else assignee_account_id
            )
            agent_value = (
                current.assignee_agent_id if assignee_agent_id is _UNSET else assignee_agent_id
            )
            if assignee_account_id not in (_UNSET, None) and assignee_agent_id in (_UNSET, None):
                agent_value = None
            if assignee_agent_id not in (_UNSET, None) and assignee_account_id in (_UNSET, None):
                account_value = None
            next_account, next_agent = _assignees(account_value, agent_value)
            if next_account != current.assignee_account_id:
                changes["assignee_account_id"] = next_account
            if next_agent != current.assignee_agent_id:
                changes["assignee_agent_id"] = next_agent
        if not changes:
            return current
        now = _now()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE work_tasks SET
                    title = ?, status = ?, priority = ?, deadline = ?,
                    assignee_account_id = ?, assignee_agent_id = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?
                """,
                (
                    next_title,
                    next_status,
                    next_priority,
                    next_deadline,
                    next_account,
                    next_agent,
                    now,
                    task_id,
                    organization_id,
                ),
            )
            _insert_activity(conn, task_id, actor_id, "updated", changes, now)
        return self.get_task(task_id, organization_id=organization_id)

    def delete_task(self, task_id: str, *, organization_id: str) -> bool:
        if self.get_task(task_id, organization_id=organization_id) is None:
            return False
        with self._conn() as conn:
            conn.execute("DELETE FROM work_task_comments WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM work_task_activity WHERE task_id = ?", (task_id,))
            conn.execute(
                "DELETE FROM work_tasks WHERE id = ? AND organization_id = ?",
                (task_id, organization_id),
            )
        return True

    def add_comment(
        self, task_id: str, *, organization_id: str, author_id: str, body: str
    ) -> WorkTaskComment:
        if self.get_task(task_id, organization_id=organization_id) is None:
            raise ValueError("Task not found")
        cleaned = str(body or "").strip()
        if not cleaned:
            raise ValueError("A comment is required")
        now = _now()
        comment_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO work_task_comments (id, task_id, author_id, body, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (comment_id, task_id, author_id, cleaned[:4000], now),
            )
            _insert_activity(
                conn,
                task_id,
                author_id,
                "commented",
                {"comment_id": comment_id},
                now,
            )
        return WorkTaskComment(
            id=comment_id,
            task_id=task_id,
            author_id=author_id,
            body=cleaned[:4000],
            created_at=datetime.fromisoformat(now),
        )

    def list_activity(self, task_id: str, *, organization_id: str) -> list[WorkTaskActivity]:
        if self.get_task(task_id, organization_id=organization_id) is None:
            raise ValueError("Task not found")
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM work_task_activity
                WHERE task_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (task_id,),
            ).fetchall()
        return [_activity_from_row(row) for row in rows]

    def open_tasks(self, project_id: str, *, organization_id: str) -> list[WorkTask]:
        return [
            task
            for task in self.list_tasks(project_id, organization_id=organization_id)
            if task.status != "done"
        ]

    def recent_decisions(
        self,
        organization_id: str,
        *,
        project_id: str,
        limit: int = 3,
    ) -> list[WorkTaskActivity]:
        if not organization_id or not project_id:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT activity.* FROM work_task_activity AS activity
                JOIN work_tasks AS task ON task.id = activity.task_id
                WHERE task.organization_id = ?
                  AND task.project_id = ?
                  AND activity.action = 'decision'
                ORDER BY activity.created_at DESC, activity.rowid DESC
                LIMIT ?
                """,
                (organization_id, project_id, max(0, int(limit))),
            ).fetchall()
        return [_activity_from_row(row) for row in rows]

    def get_activity(self, activity_id: str, *, organization_id: str) -> WorkTaskActivity | None:
        if not organization_id or not activity_id:
            return None
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT activity.* FROM work_task_activity AS activity
                JOIN work_tasks AS task ON task.id = activity.task_id
                WHERE activity.id = ? AND task.organization_id = ?
                """,
                (activity_id, organization_id),
            ).fetchone()
        return _activity_from_row(row) if row else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _title(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError("A title is required")
    return cleaned[:200]


def _choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned not in allowed:
        raise ValueError(f"Unknown {label}")
    return cleaned


def is_overdue(task: WorkTask, now: datetime | None = None) -> bool:
    """A task is overdue when its deadline has passed and it is not done."""
    if task.status == "done" or not task.deadline:
        return False
    due = _parse_time(task.deadline)
    if due is None:
        return False
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return due < moment.astimezone(timezone.utc)


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _deadline(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    try:
        datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Deadline must be an ISO date") from exc
    return cleaned


def _assignees(
    account_id: str | None, agent_id: str | None
) -> tuple[str | None, str | None]:
    account = str(account_id or "").strip() or None
    agent = str(agent_id or "").strip() or None
    if account and agent:
        raise ValueError("A task has one assignee")
    if agent:
        from agents.loader import get_role, normalize_role_id

        canonical = normalize_role_id(agent)
        if get_role(canonical) is None:
            raise ValueError("Unknown agent")
        return None, canonical
    return account, None


def _insert_activity(
    conn: sqlite3.Connection,
    task_id: str,
    actor_id: str,
    action: str,
    payload: dict[str, Any],
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO work_task_activity (id, task_id, actor_id, action, payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), task_id, actor_id, action, json.dumps(payload), created_at),
    )


def _project_from_row(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        organization_id=row["organization_id"],
        title=row["title"],
        created_by=row["created_by"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _task_from_row(row: sqlite3.Row) -> WorkTask:
    return WorkTask(
        id=row["id"],
        project_id=row["project_id"],
        organization_id=row["organization_id"],
        title=row["title"],
        status=row["status"],
        priority=row["priority"],
        deadline=row["deadline"],
        assignee_account_id=row["assignee_account_id"],
        assignee_agent_id=row["assignee_agent_id"],
        created_by=row["created_by"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _activity_from_row(row: sqlite3.Row) -> WorkTaskActivity:
    try:
        payload = json.loads(row["payload"] or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return WorkTaskActivity(
        id=row["id"],
        task_id=row["task_id"],
        actor_id=row["actor_id"],
        action=row["action"],
        payload=payload,
        created_at=datetime.fromisoformat(row["created_at"]),
    )
