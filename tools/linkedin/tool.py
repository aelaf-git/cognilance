"""LinkedIn tool: draft locally, publish via the broker integration client."""

from __future__ import annotations

from typing import Any

from core.context.request import current_conversation_id, current_mission_id
from tools.linkedin.params import (
    format_draft,
    format_post_result,
    mark_draft_sent,
    prepare_draft,
    prepare_post_params,
)
from tools.registry import ToolContext, ToolOutput
from tools.social.validate import validate_linkedin_post


async def run(action: str, *, instruction: str, params: dict[str, Any], ctx: ToolContext) -> ToolOutput:
    conv_id = current_conversation_id.get() or current_mission_id.get() or ""

    if action == "draft":
        if not conv_id:
            draft = validate_linkedin_post(
                params if params.get("text") else {"text": instruction}
            )
            return ToolOutput(text=format_draft(draft), data={**draft, "status": "draft"})
        draft = prepare_draft(instruction, params, conversation_id=conv_id)
        return ToolOutput(text=format_draft(draft), data={**draft, "status": "draft"})

    if not ctx.client.is_connected(ctx.user_id, "linkedin"):
        raise RuntimeError(
            "LinkedIn is not connected. Connect via /integrations/linkedin/connect first."
        )

    if action == "post":
        if not conv_id:
            raise RuntimeError("conversation_id is required to publish a LinkedIn draft")
        post_params = prepare_post_params(instruction, params, conversation_id=conv_id)
        result = await ctx.client.run(ctx.user_id, "linkedin", "create_post", post_params)
        mark_draft_sent(conv_id)
        return ToolOutput(
            text=format_post_result(result),
            data={**result, "status": "posted", "text": post_params.get("text")},
        )

    if action == "me":
        result = await ctx.client.run(ctx.user_id, "linkedin", "get_me", params)
        return ToolOutput(
            text=ctx.client.summarize_result("linkedin", "get_me", result), data=result
        )

    raise RuntimeError(f"Unsupported LinkedIn action: {action}")
