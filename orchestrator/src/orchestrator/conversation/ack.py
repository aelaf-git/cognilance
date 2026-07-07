"""Detect short acknowledgments that should not trigger tools or verbose replies."""

from __future__ import annotations

import re

_ACK_WORDS = frozenset(
    {
        "ok",
        "okay",
        "k",
        "great",
        "thanks",
        "thank",
        "you",
        "got",
        "it",
        "sounds",
        "good",
        "perfect",
        "nice",
        "cool",
        "awesome",
        "sure",
        "alright",
        "yep",
        "yes",
        "yeah",
        "lovely",
        "wonderful",
        "fine",
        "right",
        "noted",
        "understood",
        "appreciate",
        "cheers",
    }
)


def is_acknowledgment(query: str) -> bool:
    """True for brief affirmations like 'okay great' or 'thanks!'."""
    q = query.lower().strip()
    q = re.sub(r"[!?.]+$", "", q).strip()
    if not q:
        return False
    words = re.findall(r"[a-z']+", q)
    if not words or len(words) > 8:
        return False
    return all(word in _ACK_WORDS for word in words)


def acknowledgment_reply(*, listener_active: bool = False) -> str:
    if listener_active:
        return "You're all set — I'll let you know when a new email comes in."
    return "Got it!"
