"""Minimal Watcher event path — raise a durable Run from monitor hooks."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from core.runtime.board.store import BoardStore
from core.runtime.runs.models import RunTrigger
from core.runtime.runs.store import RunStore

logger = logging.getLogger(__name__)


def enqueue_watcher_inbox_alert(
    *,
    user_id: str,
    conversation_id: str,
    emails: list[dict[str, Any]],
    summary: str,
) -> str | None:
    """Create an event-triggered Run + watcher board task for new matching mail.

    Does not execute the graph here — the next chat/schedule cycle or an explicit
    resume can pick it up; for smoke demos the Run + board row is enough evidence.
    """
    if not emails:
        return None
    try:
        runs = RunStore()
        runs.init_db()
        board = BoardStore()
        board.init_db()

        run_id = str(uuid.uuid4())
        instruction = (
            "[Watcher event: new matching email]\n"
            f"{summary}\n\n"
            "Watcher: note the alert and suggest whether follow_up should draft a reply."
        )
        runs.create_run(
            instruction=instruction,
            thread_id=conversation_id,
            trigger=RunTrigger.EVENT,
            conversation_id=conversation_id,
            user_id=user_id,
            run_id=run_id,
        )
        board.create_task(
            run_id=run_id,
            title="Inbox alert",
            instruction=instruction,
            assignee_role="watcher",
        )
        runs.append_step(
            run_id,
            kind="task_created",
            text="Inbox alert",
            data={"emails": len(emails), "role": "watcher"},
        )
        logger.info("Watcher event Run %s for conversation %s", run_id, conversation_id)
        return run_id
    except Exception:
        logger.exception("Failed to enqueue watcher inbox alert")
        return None
