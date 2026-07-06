"""Thinking node — simple path handler."""

from __future__ import annotations

from orchestrator.context import current_user_id
from orchestrator.integrations.client import IntegrationClient
from orchestrator.nodes.thinking import run_thinking
from orchestrator.state import State
from orchestrator.streaming import emit, emit_status


async def thinking_node(state: State) -> dict:
    conversation = state.get("messages", [])
    user_id = current_user_id.get()
    capabilities = IntegrationClient().capabilities_context(user_id)
    emit_status("Thinking Agent answering…")
    text, data = await run_thinking(
        stream=True,
        conversation=conversation,
        capabilities=capabilities,
    )
    emit("answer_done", text=text)
    return {
        "final_text": text,
        "final_data": data,
        "answer_streamed": True,
        "subtask_results": [],
    }
