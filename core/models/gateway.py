"""Shared helpers: Gemini LLM factory and message utilities."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

import core.context.env  # noqa: F401

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_THINKING_LEVEL = "medium"
_THINKING_LEVELS = frozenset({"minimal", "low", "medium", "high"})
_THOUGHT_TYPES = frozenset({"thinking", "reasoning"})


def gemini_model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)


def gemini_thinking_level() -> str:
    raw = os.getenv("GEMINI_THINKING_LEVEL", DEFAULT_THINKING_LEVEL).strip().lower()
    if raw in _THINKING_LEVELS:
        return raw
    return DEFAULT_THINKING_LEVEL


def gemini_api_key() -> str:
    from core.config import get_settings

    key = get_settings().gemini_api_key
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) to use Gemini.")
    return key


def split_model_content(content: Any) -> tuple[str, str]:
    """Separate a Gemini thought summary from the answer text."""
    if content is None:
        return "", ""
    if isinstance(content, str):
        return "", content
    if not isinstance(content, list):
        return "", str(content)
    thoughts: list[str] = []
    answers: list[str] = []
    for part in content:
        if isinstance(part, str):
            if part:
                answers.append(part)
            continue
        if not isinstance(part, dict):
            text = str(part).strip()
            if text:
                answers.append(text)
            continue
        kind = str(part.get("type") or "")
        if kind in _THOUGHT_TYPES:
            thought = part.get("thinking") or part.get("reasoning") or ""
            if thought:
                thoughts.append(str(thought))
            continue
        text = part.get("text") or ""
        if text:
            answers.append(str(text))
    return "\n".join(thoughts), "\n".join(answers)


def publish_thoughts(message: Any) -> None:
    """Emit the model's thought summary and leave only the answer on the message."""
    content = getattr(message, "content", None)
    thought, answer = split_model_content(content)
    if thought:
        from pipelines.shared.streaming import reveal_text

        reveal_text(thought, event="thinking")
    if isinstance(content, list):
        message.content = answer


class _StructuredThoughts:
    """Structured calls return the parsed object and emit thoughts from the raw message."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return _unwrap_structured(await self._inner.ainvoke(*args, **kwargs))

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return _unwrap_structured(self._inner.invoke(*args, **kwargs))


def _unwrap_structured(result: Any) -> Any:
    if isinstance(result, dict) and "raw" in result and "parsed" in result:
        raw = result.get("raw")
        if raw is not None:
            publish_thoughts(raw)
        error = result.get("parsing_error")
        if result.get("parsed") is None and error is not None:
            raise error
        return result.get("parsed")
    publish_thoughts(result)
    return result


class ReasoningLLM:
    """Gemini chat model that reasons and surfaces its thought summary."""

    def __init__(self, inner: ChatGoogleGenerativeAI) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        message = await self._inner.ainvoke(*args, **kwargs)
        publish_thoughts(message)
        return message

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        message = self._inner.invoke(*args, **kwargs)
        publish_thoughts(message)
        return message

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _StructuredThoughts:
        kwargs["include_raw"] = True
        return _StructuredThoughts(self._inner.with_structured_output(schema, **kwargs))


def get_llm(temperature: float = 0.2) -> ReasoningLLM:
    inner = ChatGoogleGenerativeAI(
        model=gemini_model_name(),
        api_key=gemini_api_key(),
        temperature=temperature,
        include_thoughts=True,
        thinking_level=gemini_thinking_level(),
    )
    return ReasoningLLM(inner)


def get_structured_llm(schema: type[BaseModel], temperature: float = 0.2) -> Any:
    """Gemini native JSON schema is more reliable than tool-call extraction."""
    return get_llm(temperature=temperature).with_structured_output(
        schema,
        method="json_schema",
    )


def last_user_text(messages: list[BaseMessage]) -> str:
    """Return the text of the most recent human message (or last message)."""
    for message in reversed(messages):
        if getattr(message, "type", None) == "human":
            return _content_to_text(message.content)
    if messages:
        return _content_to_text(messages[-1].content)
    return ""


def to_chat_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    """Convert LangChain messages to OpenAI-style role/content dicts."""
    result: list[dict[str, str]] = []
    for message in messages:
        role = getattr(message, "type", None)
        if role == "human":
            result.append({"role": "user", "content": _content_to_text(message.content)})
        elif role == "ai":
            result.append({"role": "assistant", "content": _content_to_text(message.content)})
    return result


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ]
        return "\n".join(p for p in parts if p)
    return str(content)
