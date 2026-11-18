"""Signed-in account identity for coordinator turns."""

from __future__ import annotations

import sqlite3

from core.context.request import current_user_id
from core.context.users.accounts import AccountStore

_store: AccountStore | None = None


def _accounts() -> AccountStore:
    global _store
    if _store is None:
        _store = AccountStore()
    return _store


def signed_in_display_name(user_id: str | None = None) -> str:
    """Display name from account settings, or empty when nobody is signed in."""
    uid = (user_id if user_id is not None else current_user_id.get() or "").strip()
    if not uid or uid == "default":
        return ""
    try:
        account = _accounts().get_by_id(uid)
    except sqlite3.Error:
        return ""
    if account is None:
        return ""
    return account.display_name.strip()
