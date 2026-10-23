"""Google Docs tool: parameters are enriched by the model, writes go through the broker."""

from __future__ import annotations

from typing import Any

from tools.google_docs.params import prepare_google_doc_params
from tools.presenters import format_document_result
from tools.registry import ToolContext, ToolOutput

_ACTION_MAP = {
    "create": "create_document",
    "write": "write_document",
    "read": "read_document",
}


async def run(action: str, *, instruction: str, params: dict[str, Any], ctx: ToolContext) -> ToolOutput:
    docs_action = _ACTION_MAP.get(action, action)
    if not ctx.client.is_connected(ctx.user_id, "google-drive"):
        raise RuntimeError("Google Drive is not connected")
    params = await prepare_google_doc_params(docs_action, instruction, params)
    result = await ctx.client.run(ctx.user_id, "google-drive", docs_action, params)
    return ToolOutput(text=format_document_result(result), data=result)
