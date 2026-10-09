"""Short-lived callback tokens for hired agents to call orchestrator tools."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from typing import Any

from orchestrator.integrations.oauth import public_base_url

DEFAULT_TTL_SECONDS = 900  # 15 minutes

GMAIL_SCOPES = frozenset({"gmail:send", "gmail:read", "gmail:search"})
DOCS_SCOPES = frozenset({"docs:read", "docs:write"})

SCOPE_BY_SKILL: dict[str, list[str]] = {
    "email-writing": sorted(GMAIL_SCOPES),
    "proposal-writing": sorted(DOCS_SCOPES),
    "docs-creating": sorted(DOCS_SCOPES),
}


def _secret() -> bytes:
    return (
        os.getenv("TOOL_PROXY_SIGNING_KEY")
        or os.getenv("ORCHESTRATOR_SESSION_SECRET")
        or os.getenv("INTEGRATION_ENCRYPTION_KEY")
        or "cognilance-dev-insecure-tool-proxy"
    ).encode()


def _sign(payload_b64: str) -> str:
    digest = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{digest}"


def _verify_token(token: str) -> dict[str, Any] | None:
    if "." not in token:
        return None
    payload_b64, digest = token.rsplit(".", 1)
    expected = hmac.new(_secret(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, expected):
        return None
    try:
        payload = json.loads(urlsafe_b64decode(payload_b64.encode()).decode())
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    exp = int(payload.get("exp", 0))
    if exp < int(time.time()):
        return None
    return payload


@dataclass(frozen=True)
class ToolProxyGrant:
    base_url: str
    callback_token: str
    task_id: str
    trace_id: str
    user_id: str
    scopes: list[str]

    def to_input_data(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "callback_token": self.callback_token,
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "scopes": self.scopes,
        }


def issue_grant(
    *,
    user_id: str,
    task_id: str,
    trace_id: str,
    scopes: list[str],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> ToolProxyGrant:
    payload = {
        "jti": str(uuid.uuid4()),
        "user_id": user_id,
        "task_id": task_id,
        "trace_id": trace_id,
        "scopes": sorted(set(scopes)),
        "exp": int(time.time()) + ttl_seconds,
    }
    payload_b64 = urlsafe_b64encode(json.dumps(payload).encode()).decode()
    token = _sign(payload_b64)
    return ToolProxyGrant(
        base_url=public_base_url(),
        callback_token=token,
        task_id=task_id,
        trace_id=trace_id,
        user_id=user_id,
        scopes=payload["scopes"],
    )


def scopes_for_skill(skill: str) -> list[str]:
    return list(SCOPE_BY_SKILL.get(skill, []))


def validate_callback(
    token: str,
    *,
    task_id: str,
    required_scope: str,
) -> dict[str, Any]:
    payload = _verify_token(token)
    if payload is None:
        raise PermissionError("Invalid or expired callback token")
    if str(payload.get("task_id")) != str(task_id):
        raise PermissionError("Callback token does not match task_id")
    scopes = payload.get("scopes") or []
    if required_scope not in scopes:
        raise PermissionError(f"Scope not granted: {required_scope}")
    return payload
