"""Thinking node — simple path handler."""

from __future__ import annotations

from orchestrator.llm import last_user_text
from orchestrator.nodes.thinking import run_thinking
from orchestrator.state import State
from orchestrator.streaming import emit, emit_status


async def thinking_node(state: State) -> dict:
    query = last_user_text(state.get("messages", []))
    emit_status("Thinking Agent answering…")
    text, data = await run_thinking(query, stream=True)
    emit("answer_done", text=text)
    return {
        "final_text": text,
        "final_data": data,
        "answer_streamed": True,
        "subtask_results": [],
    }
