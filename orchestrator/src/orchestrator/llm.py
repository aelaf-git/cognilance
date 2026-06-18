"""Shared helpers: Groq LLM factory and message utilities."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def get_llm(temperature: float = 0.2) -> ChatGroq:
    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        api_key=os.environ["GROQ_API_KEY"],
        temperature=temperature,
    )


def last_user_text(messages: list[BaseMessage]) -> str:
    """Return the text of the most recent human message (or last message)."""
    for message in reversed(messages):
        if getattr(message, "type", None) == "human":
            return _content_to_text(message.content)
    if messages:
        return _content_to_text(messages[-1].content)
    return ""


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
