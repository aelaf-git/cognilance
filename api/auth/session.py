"""HMAC cookie sessions keyed by account id."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Request, Response

from core.config import session_secret_bytes

COOKIE_NAME = "coordinator_uid"


def _secret() -> bytes:
    return session_secret_bytes()


def _sign(value: str) -> str:
    digest = hmac.new(_secret(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{digest}"


def _verify(signed: str) -> str | None:
    if "." not in signed:
        return None
    value, digest = signed.rsplit(".", 1)
    expected = hmac.new(_secret(), value.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(digest, expected):
        return value
    return None


def get_user_id(request: Request) -> str | None:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    return _verify(cookie)


def resolve_user_id(request: Request) -> str | None:
    """Return the verified account id, or None when anonymous."""
    return get_user_id(request)


def set_user_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        _sign(user_id),
        httponly=True,
        samesite="lax",
        max_age=365 * 24 * 3600,
        path="/",
    )


def clear_user_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
