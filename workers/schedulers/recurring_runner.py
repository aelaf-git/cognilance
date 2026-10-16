"""Execute a recurring task via the durable coordinator graph."""

from __future__ import annotations

import uuid
from typing import Any

from core.context.request import current_conversation_id, current_mission_id, current_user_id, current_user_timezone
from core.context.conversations.store import ConversationStore
from core.runtime.runs.models import RunTrigger
from core.context.users.timezone import activate_user_timezone
from core.runtime.runner import stream_mission_graph


async def run_recurring_instruction(
    *,
    user_id: str,
    conversation_id: str,
    instruction: str,
    mission_id: str | None = None,
) -> dict[str, Any]:
    """Enqueue and run one schedule-triggered durable Run; returns final text or error."""
    run_prompt = (
        f"[Scheduled background run]\n{instruction}\n\n"
        "Execute this task now using available tools. "
        "Reply with a brief, user-facing summary of what you found or did."
    )

    final_text: str | None = None
    had_error = False
    error_message: str | None = None
    run_id = mission_id or str(uuid.uuid4())

    async def on_event(event: dict[str, Any]) -> None:
        nonlocal final_text, had_error, error_message
        if event.get("event") == "final":
            final_text = str(event.get("text") or "").strip() or None
        if event.get("event") == "error":
            had_error = True
            error_message = str(event.get("message") or "Task failed")

    conv_store = ConversationStore()
    history = conv_store.to_langchain_messages(conversation_id)

    user_token = current_user_id.set(user_id)
    tz_token = activate_user_timezone(user_id)
    conv_token = current_conversation_id.set(conversation_id)
    mission_token = current_mission_id.set(run_id)

    try:
        async for _line in stream_mission_graph(
            run_prompt,
            conversation_id,
            history=history,
            on_event=on_event,
            use_checkpointer=True,
            run_id=run_id,
            user_id=user_id,
            trigger=RunTrigger.SCHEDULE,
        ):
            pass
    finally:
        current_user_timezone.reset(tz_token)
        current_user_id.reset(user_token)
        current_conversation_id.reset(conv_token)
        current_mission_id.reset(mission_token)

    return {
        "text": final_text,
        "had_error": had_error,
        "error": error_message,
        "run_id": run_id,
    }
