"""Which coordinator paths may be called without an account cookie."""

from __future__ import annotations

from fastapi import Request


def is_public_request(request: Request) -> bool:
    path = request.url.path.rstrip("/") or "/"
    method = request.method.upper()

    if path in {"/", "/health", "/skills/online", "/marketplace/agents"}:
        return True
    if path in {"/icon.png", "/icon-light.png"}:
        return True
    if path.startswith("/integrations/logos/"):
        return True
    if path.startswith("/tools/"):
        return True
    if path == "/integrations/oauth/callback" and method == "GET":
        return True
    if path == "/auth/register" and method == "POST":
        return True
    if path == "/auth/login" and method == "POST":
        return True
    return False
