"""Model gateway — single place that talks to LLM providers."""

from core.models.gateway import get_llm, get_structured_llm, last_user_text, to_chat_messages
from core.models.thinking import run_thinking

__all__ = ["get_llm", "get_structured_llm", "last_user_text", "to_chat_messages", "run_thinking"]
