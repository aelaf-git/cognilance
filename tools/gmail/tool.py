"""Gmail tool: draft locally, send/read via the broker's integration client."""

from __future__ import annotations

from typing import Any

from core.context.request import current_conversation_id, current_mission_id
from tools.gmail.params import (
    compose_email_content,
    format_email_draft,
    format_send_email_result,
    mark_email_draft_sent,
    prepare_compose_email,
    prepare_send_email_params,
)
from tools.presenters import format_gmail_list_result
from tools.registry import ToolContext, ToolOutput

_ACTION_MAP = {
    "draft": "compose_email",
    "send": "send_email",
    "search": "search_emails",
    "list": "list_emails",
    "read": "read_email",
}


async def run(action: str, *, instruction: str, params: dict[str, Any], ctx: ToolContext) -> ToolOutput:
    gmail_action = _ACTION_MAP.get(action, action)
    # Drafts are keyed by conversation; fall back to the run id for bare graph runs.
    conv_id = current_conversation_id.get() or current_mission_id.get() or ""

    if gmail_action == "compose_email":
        if conv_id:
            draft = await prepare_compose_email(instruction, params, conversation_id=conv_id)
        else:
            draft = await compose_email_content(instruction, partial=params)
        return ToolOutput(text=format_email_draft(draft), data={**draft, "status": "draft"})

    if not ctx.client.is_connected(ctx.user_id, "gmail"):
        raise RuntimeError("Gmail is not connected")

    if gmail_action == "send_email":
        params = await prepare_send_email_params(instruction, params, conversation_id=conv_id)
        result = await ctx.client.run(ctx.user_id, "gmail", gmail_action, params)
        if conv_id:
            mark_email_draft_sent(conv_id)
        return ToolOutput(text=format_send_email_result(result), data=result)

    result = await ctx.client.run(ctx.user_id, "gmail", gmail_action, params)
    if gmail_action in {"list_emails", "search_emails"}:
        return ToolOutput(text=format_gmail_list_result(result), data=result)
    return ToolOutput(text=ctx.client.summarize_result("gmail", gmail_action, result), data=result)
