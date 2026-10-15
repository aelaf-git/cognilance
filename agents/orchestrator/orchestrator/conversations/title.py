"""Short conversation titles from the first user prompt."""

from __future__ import annotations

import logging
import re

_log = logging.getLogger(__name__)

_MAX_TITLE = 80


def fallback_conversation_title(prompt: str) -> str:
    cleaned = re.sub(r"\s+", " ", (prompt or "").strip())
    if not cleaned:
        return "New conversation"
    return cleaned[:_MAX_TITLE]


def _sanitize_title(raw: str, *, fallback: str) -> str:
    text = (raw or "").strip()
    text = text.splitlines()[0].strip() if text else ""
    text = text.strip("\"'`“”‘’")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.rstrip(" .,:;")
    if text.lower().startswith("conversation about "):
        text = text[19:].strip()
    if not text:
        return fallback
    return text[:_MAX_TITLE]


async def paraphrase_conversation_title(prompt: str) -> str:
    """Return a short paraphrased title for the conversation's first prompt."""
    fallback = fallback_conversation_title(prompt)
    if not prompt or not prompt.strip():
        return fallback
    try:
        from pipeline.llm import get_llm

        llm = get_llm(temperature=0.3)
        response = await llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Write a short conversation title from the user's first message. "
                        "Paraphrase and summarize the request in about 3 to 8 words "
                        "(max ~60 characters). Title case is fine. "
                        "No quotes, no trailing punctuation, no markdown, "
                        "and do not start with 'Conversation about'."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt.strip()[:2000],
                },
            ]
        )
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = " ".join(
                str(part.get("text") if isinstance(part, dict) else part)
                for part in content
            )
        return _sanitize_title(str(content), fallback=fallback)
    except Exception as exc:
        _log.warning("conversation title paraphrase failed: %s", exc)
        return fallback
