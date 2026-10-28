"""Reddit tool: draft locally, submit via the broker integration client."""

from __future__ import annotations

from typing import Any

from core.context.request import current_conversation_id, current_mission_id
from tools.reddit.params import (
    format_draft,
    format_post_result,
    mark_draft_sent,
    prepare_draft,
    prepare_post_params,
)
from tools.registry import ToolContext, ToolOutput
from tools.social.validate import validate_reddit_post


async def run(action: str, *, instruction: str, params: dict[str, Any], ctx: ToolContext) -> ToolOutput:
    conv_id = current_conversation_id.get() or current_mission_id.get() or ""

    if action == "draft":
        if not conv_id:
            draft = validate_reddit_post(params)
            return ToolOutput(text=format_draft(draft), data={**draft, "status": "draft"})
        draft = prepare_draft(instruction, params, conversation_id=conv_id)
        return ToolOutput(text=format_draft(draft), data={**draft, "status": "draft"})

    if not ctx.client.is_connected(ctx.user_id, "reddit"):
        raise RuntimeError(
            "Reddit is not connected. Connect via /integrations/reddit/connect first."
        )

    if action == "post":
        if not conv_id:
            raise RuntimeError("conversation_id is required to submit a Reddit draft")
        post_params = prepare_post_params(instruction, params, conversation_id=conv_id)
        result = await ctx.client.run(ctx.user_id, "reddit", "submit_post", post_params)
        mark_draft_sent(conv_id)
        return ToolOutput(
            text=format_post_result(result),
            data={**result, "status": "posted", **post_params},
        )

    if action == "me":
        result = await ctx.client.run(ctx.user_id, "reddit", "get_me", params)
        return ToolOutput(
            text=ctx.client.summarize_result("reddit", "get_me", result), data=result
        )

    raise RuntimeError(f"Unsupported Reddit action: {action}")
