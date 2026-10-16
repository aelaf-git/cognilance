"""Calendar tool — read-only listing via the broker."""

from __future__ import annotations

from typing import Any

from tools.calendar.params import prepare_calendar_list_params
from tools.presenters import format_calendar_list_result
from tools.registry import ToolContext, ToolOutput


async def run(action: str, *, instruction: str, params: dict[str, Any], ctx: ToolContext) -> ToolOutput:
    if action != "list":
        raise RuntimeError(f"Unknown calendar action: {action}")
    if not ctx.client.is_connected(ctx.user_id, "google-calendar"):
        raise RuntimeError("Google Calendar is not connected")
    params = prepare_calendar_list_params(instruction, params, user_id=ctx.user_id)
    result = await ctx.client.run(ctx.user_id, "google-calendar", "list_events", params)
    return ToolOutput(text=format_calendar_list_result(result), data=result)
