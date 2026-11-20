"""Organization rows for the plan prompt, capped so a long history is not pasted in full."""

from __future__ import annotations

from typing import Any

from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.projects.store import Project, ProjectStore, WorkTaskActivity
from core.context.request import current_conversation_id, current_mission_id
from core.runtime.missions.store import MissionStore
from core.runtime.runs.store import RunStore
from pipelines.shared.state import State

CONTEXT_BUDGET = 2000
_SNIPPET = 240
_DECISIONS = 3
_NOTES = 3
_MESSAGES = 20


def _organization_id(state: State) -> str:
    run_id = str(state.get("run_id") or current_mission_id.get() or "").strip()
    if not run_id:
        return ""
    mission = MissionStore().get_mission(run_id)
    if mission and mission.organization_id:
        return str(mission.organization_id)
    run = RunStore().get_run(run_id)
    if run and run.organization_id:
        return str(run.organization_id)
    return ""


def _conversation_id(state: State) -> str:
    current = str(current_conversation_id.get() or "").strip()
    if current:
        return current
    run_id = str(state.get("run_id") or current_mission_id.get() or "").strip()
    if not run_id:
        return ""
    run = RunStore().get_run(run_id)
    if run and run.conversation_id:
        return str(run.conversation_id)
    return ""


def _clip(text: str) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= _SNIPPET:
        return cleaned
    return cleaned[: _SNIPPET - 1].rstrip() + "…"


def _line(source_id: str, text: str) -> str:
    return f"[source:{source_id}] {_clip(text)}"


def _fit(lines: list[str], budget: int) -> tuple[list[str], int]:
    kept: list[str] = []
    used = 0
    for line in lines:
        extra = len(line) + (1 if kept else 0)
        if used + extra > budget:
            break
        kept.append(line)
        used += extra
    return kept, used


def _mentioned_project(projects: list[Project], query: str) -> Project | None:
    haystack = query.lower()
    matches = [item for item in projects if item.title.strip() and item.title.lower() in haystack]
    if not matches:
        return None
    return max(matches, key=lambda item: len(item.title))


def _decision_text(activity: WorkTaskActivity) -> str:
    payload = activity.payload or {}
    for key in ("text", "body", "summary"):
        text = str(payload.get(key) or "").strip()
        if text:
            return text
    return str(payload)


def organization_context(state: State, query: str) -> str:
    """Open tasks, decisions, and notes for a named project, plus capped history."""
    organization_id = _organization_id(state)
    if not organization_id:
        return ""
    projects = ProjectStore()
    projects.init_db()
    orgs = OrgStore()
    orgs.init_db()
    conversations = ConversationStore()
    conversations.init_db()

    priority: list[str] = []
    mentioned = _mentioned_project(projects.list_projects(organization_id), query)
    if mentioned is not None:
        for task in projects.open_tasks(mentioned.id, organization_id=organization_id):
            deadline = f", due {task.deadline}" if task.deadline else ""
            priority.append(_line(task.id, f"{task.title} ({task.status}{deadline})"))
        for activity in projects.recent_decisions(
            organization_id, project_id=mentioned.id, limit=_DECISIONS
        ):
            priority.append(_line(activity.id, _decision_text(activity)))
        for note in orgs.list_notes(organization_id, limit=_NOTES):
            priority.append(_line(note.id, note.body))

    kept, used = _fit(priority, CONTEXT_BUDGET)
    conversation_id = _conversation_id(state)
    conversation = conversations.get_conversation(conversation_id) if conversation_id else None
    if conversation and conversation.organization_id == organization_id:
        messages = conversations.list_messages(conversation_id, limit=_MESSAGES)
        chosen: list[str] = []
        message_used = 0
        remaining = CONTEXT_BUDGET - used - (1 if kept else 0)
        for message in reversed(messages):
            line = _line(str(message.id), f"{message.role}: {message.content}")
            extra = len(line) + (1 if chosen else 0)
            if message_used + extra > remaining:
                break
            chosen.append(line)
            message_used += extra
        kept.extend(reversed(chosen))
    return "\n".join(kept)


def resolve_source(organization_id: str, source_id: str) -> Any:
    """Return this organization's message, work task, activity, or note for a source id."""
    source = str(source_id or "").strip()
    if not organization_id or not source:
        return None
    projects = ProjectStore()
    task = projects.get_task(source, organization_id=organization_id)
    if task is not None:
        return task
    activity = projects.get_activity(source, organization_id=organization_id)
    if activity is not None:
        return activity
    note = OrgStore().get_note(source, organization_id=organization_id)
    if note is not None:
        return note
    if source.isdigit():
        message = ConversationStore().get_message(int(source))
        if message is None:
            return None
        conversation = ConversationStore().get_conversation(message.conversation_id)
        if conversation and conversation.organization_id == organization_id:
            return message
    return None
