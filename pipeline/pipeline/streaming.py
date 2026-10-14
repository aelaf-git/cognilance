"""Helpers for streaming orchestrator events to the chat UI."""

from __future__ import annotations

from typing import Any
from langgraph.config import get_stream_writer


def emit(event: str, **data: Any) -> None:
    """Emit a custom stream event when running inside the LangGraph context."""
    try:
        get_stream_writer()({"event": event, **data})
    except RuntimeError:
        pass


def emit_status(message: str) -> None:
    emit("status", message=message)


def chunk_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ]
        return "".join(parts)
    return str(content)


async def stream_llm(
    llm: Any,
    messages: list[dict[str, str]],
    *,
    event: str = "answer",
) -> str:
    """Stream LLM tokens as custom events and return the full text."""
    parts: list[str] = []
    async for chunk in llm.astream(messages):
        delta = chunk_text(getattr(chunk, "content", chunk))
        if not delta:
            continue
        parts.append(delta)
        emit(event, delta=delta)
    return "".join(parts)


def reveal_text(text: str, *, event: str = "answer", chunk_size: int = 12) -> None:
    """Emit pre-generated text in chunks (for hired agent responses)."""
    if not text:
        return
    for index in range(0, len(text), chunk_size):
        emit(event, delta=text[index : index + chunk_size])
