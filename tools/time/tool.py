"""Time tool: deterministic, no network."""

from __future__ import annotations

from typing import Any

from core.context.datetime_util import current_time_context, format_current_time_summary
from tools.registry import ToolContext, ToolOutput


async def run(action: str, *, instruction: str, params: dict[str, Any], ctx: ToolContext) -> ToolOutput:
    if action != "now":
        raise RuntimeError(f"Unknown time action: {action}")
    data = current_time_context(user_id=ctx.user_id)
    return ToolOutput(text=format_current_time_summary(data), data=data)
