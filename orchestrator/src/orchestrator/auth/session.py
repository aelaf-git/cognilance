"""Anonymous per-browser user sessions for integration scoping."""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid

from fastapi import Request, Response

COOKIE_NAME = "orchestrator_uid"


def _secret() -> bytes:
    return (
        os.getenv("ORCHESTRATOR_SESSION_SECRET")
        or os.getenv("INTEGRATION_ENCRYPTION_KEY")
        or "cognilance-dev-insecure-session"
    ).encode()


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


def set_user_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        _sign(user_id),
        httponly=True,
        samesite="lax",
        max_age=365 * 24 * 3600,
        path="/",
    )


def resolve_user_id(request: Request) -> str:
    return get_user_id(request) or str(uuid.uuid4())
