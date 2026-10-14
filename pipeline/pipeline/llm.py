"""Shared helpers: Groq LLM factory and message utilities."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

import orchestrator.env  # noqa: F401

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def groq_model_name() -> str:
    return os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)


def structured_output_method(model: str | None = None) -> str:
    """gpt-oss on Groq often emits plain text instead of a required tool call."""
    name = (model or groq_model_name()).lower()
    if "gpt-oss" in name:
        return "json_schema"
    return "function_calling"


def get_llm(temperature: float = 0.2) -> ChatGroq:
    return ChatGroq(
        model=groq_model_name(),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=temperature,
    )


def get_structured_llm(schema: type[BaseModel], temperature: float = 0.2) -> Any:
    return get_llm(temperature=temperature).with_structured_output(
        schema,
        method=structured_output_method(),
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
