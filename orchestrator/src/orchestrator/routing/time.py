"""Route explicit time queries to the built-in time tool."""

from __future__ import annotations

from orchestrator.state import Subtask


def _mentions(query: str, *terms: str) -> bool:
    q = query.lower()
    return any(term in q for term in terms)


def time_subtasks_for_query(query: str) -> list[Subtask] | None:
    q = query.lower().strip()
    if not _mentions(
        q,
        "what time",
        "what's the time",
        "whats the time",
        "current time",
        "what date",
        "what's the date",
        "what day is it",
        "what day is today",
        "time is it",
    ):
        return None
    return [
        {
            "id": "time-now",
            "title": "Get current time",
            "instruction": query,
            "tool": "time",
            "action": "now",
            "params": {},
            "assignee": "time",
            "depends_on": [],
        }
    ]
