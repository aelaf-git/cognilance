"""Monitor intent detection for on-demand background listeners."""

from __future__ import annotations

_MONITOR_HINTS = (
    "notify me when",
    "notify me if",
    "alert me when",
    "alert me if",
    "let me know when",
    "tell me when",
    "keep listening",
    "keep monitoring",
    "watch my inbox",
    "watch for new",
    "listen for new",
    "listening for new",
    "new emails arrive",
    "new email arrives",
    "when new emails",
    "when a new email",
    "until i stop",
    "until i tell you to stop",
)

_STOP_HINTS = (
    "stop listening",
    "stop monitoring",
    "stop watching",
    "cancel watcher",
    "cancel listening",
    "unsubscribe",
    "no longer listen",
    "don't listen",
    "do not listen",
)


def is_stop_monitor_request(query: str) -> bool:
    q = query.lower().strip()
    return any(hint in q for hint in _STOP_HINTS)


def is_monitor_request(query: str) -> bool:
    q = query.lower().strip()
    if is_stop_monitor_request(q):
        return False
    # One-shot questions, not background listeners
    one_shot_hints = (
        "let me know if",
        "tell me if",
        "is there",
        "are there",
        "do i have",
        "any meetings",
        "any events",
    )
    if any(hint in q for hint in one_shot_hints):
        return False
    return any(hint in q for hint in _MONITOR_HINTS)


def monitor_integration_for_query(query: str) -> str | None:
    q = query.lower()
    if any(t in q for t in ("email", "emails", "inbox", "gmail", "mailbox", "mail")):
        return "gmail"
    if any(t in q for t in ("calendar", "event", "meeting")):
        return "google-calendar"
    return "gmail"
