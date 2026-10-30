"""Shared helpers: Gemini LLM factory and message utilities."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

import core.context.env  # noqa: F401

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


def gemini_model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)


def gemini_api_key() -> str:
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) to use Gemini.")
    return key


def get_llm(temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=gemini_model_name(),
        api_key=gemini_api_key(),
        temperature=temperature,
    )


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
