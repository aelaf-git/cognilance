"""Execute a recurring task via the orchestrator graph."""

from __future__ import annotations

from typing import Any

from orchestrator.context import current_conversation_id, current_mission_id, current_user_id, current_user_timezone
from orchestrator.users.timezone import activate_user_timezone
from orchestrator.conversations.store import ConversationStore
from orchestrator.runtime.runner import stream_mission_graph


async def run_recurring_instruction(
    *,
    user_id: str,
    conversation_id: str,
    instruction: str,
    mission_id: str | None = None,
) -> dict[str, Any]:
    """Run one scheduled execution; returns final text or error."""
    run_prompt = (
        f"[Scheduled background run]\n{instruction}\n\n"
        "Execute this task now using available tools. "
        "Reply with a brief, user-facing summary of what you found or did."
    )

    final_text: str | None = None
    had_error = False
    error_message: str | None = None

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
    mission_token = current_mission_id.set(mission_id or "")

    try:
        async for _line in stream_mission_graph(
            run_prompt,
            conversation_id,
            history=history,
            on_event=on_event,
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
    }
