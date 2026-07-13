"""Per-user timezone resolution and request activation."""

from __future__ import annotations

import os
import re
from contextvars import Token
from typing import Any

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from orchestrator.context import current_user_timezone
from orchestrator.users.store import UserPreferencesStore

DEFAULT_TIMEZONE = "UTC"
_TZ_NAME_RE = re.compile(r"^[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*$")
_store: UserPreferencesStore | None = None


def _preferences_store() -> UserPreferencesStore:
    global _store
    if _store is None:
        _store = UserPreferencesStore()
    return _store


def normalize_timezone_name(name: str | None) -> str | None:
    """Validate an IANA timezone name; return None if invalid."""
    if not name:
        return None
    raw = str(name).strip()
    if not raw or len(raw) > 64 or not _TZ_NAME_RE.match(raw):
        return None
    try:
        ZoneInfo(raw)
    except ZoneInfoNotFoundError:
        return None
    return raw


def deployment_default_timezone() -> str:
    """Optional server-wide fallback when a user has no stored timezone."""
    return normalize_timezone_name(os.getenv("ORCHESTRATOR_TIMEZONE")) or DEFAULT_TIMEZONE


def get_stored_user_timezone(user_id: str | None) -> str | None:
    if not user_id:
        return None
    return normalize_timezone_name(_preferences_store().get_timezone(user_id))


def resolve_user_timezone_name(
    *,
    user_id: str | None = None,
    explicit: str | None = None,
    use_context: bool = True,
) -> str:
    """
    Pick the effective timezone for a user.

    Priority: explicit param → request context → stored user pref → deployment default → UTC.
    """
    normalized = normalize_timezone_name(explicit)
    if normalized:
        return normalized
    if use_context:
        ctx_tz = normalize_timezone_name(current_user_timezone.get())
        if ctx_tz:
            return ctx_tz
    stored = get_stored_user_timezone(user_id)
    if stored:
        return stored
    return deployment_default_timezone()


def persist_user_timezone(user_id: str, timezone_name: str | None) -> str | None:
    """Save a client-reported timezone when valid."""
    normalized = normalize_timezone_name(timezone_name)
    if not normalized or not user_id:
        return None
    _preferences_store().set_timezone(user_id, normalized)
    return normalized


def activate_user_timezone(
    user_id: str,
    *,
    from_client: str | None = None,
) -> Token[str]:
    """Set request-scoped timezone from client hint or stored preference."""
    if from_client:
        persisted = persist_user_timezone(user_id, from_client)
        tz = persisted or resolve_user_timezone_name(user_id=user_id, use_context=False)
    else:
        tz = resolve_user_timezone_name(user_id=user_id, use_context=False)
    return current_user_timezone.set(tz)


def client_timezone_from_request(
    request: Any,
    payload: dict[str, Any] | None = None,
) -> str | None:
    """Read timezone from header or JSON body."""
    header = request.headers.get("X-User-Timezone") if request is not None else None
    if header:
        return str(header).strip() or None
    if payload:
        body_tz = payload.get("timezone")
        if body_tz:
            return str(body_tz).strip() or None
    return None
