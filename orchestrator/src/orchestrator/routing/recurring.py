"""Route recurring background task requests to subscription subtasks."""

from __future__ import annotations

from orchestrator.state import Subtask
from orchestrator.subscriptions.recurring_intent import (
    is_recurring_task_request,
    is_stop_recurring_request,
)
from orchestrator.subscriptions.recurring_params import prepare_recurring_subscribe_params


def recurring_subtasks_for_query(query: str) -> list[Subtask] | None:
    if is_stop_recurring_request(query):
        return [
            {
                "id": "stop-recurring",
                "title": "Stop recurring task",
                "instruction": query,
                "tool": "recurring",
                "action": "unsubscribe",
                "params": {},
                "assignee": "recurring",
                "depends_on": [],
            }
        ]

    if not is_recurring_task_request(query):
        return None

    params = prepare_recurring_subscribe_params(query, {})
    return [
        {
            "id": "recurring-task",
            "title": "Schedule recurring task",
            "instruction": query,
            "tool": "recurring",
            "action": "subscribe",
            "params": params,
            "assignee": "recurring",
            "depends_on": [],
        }
    ]
