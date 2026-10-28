"""Shared validation for social post drafts before any network write."""

from __future__ import annotations

import re
from typing import Any

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

X_MAX_CHARS = 280
REDDIT_TITLE_MAX = 300
LINKEDIN_MAX_CHARS = 3000


def clean_text(value: Any) -> str:
    text = str(value or "")
    text = _CONTROL_RE.sub("", text)
    return text.strip()


def require_nonempty(text: str, field: str = "text") -> str:
    cleaned = clean_text(text)
    if not cleaned:
        raise RuntimeError(f"{field} is required and cannot be empty")
    return cleaned


def reject_media_fields(params: dict[str, Any]) -> None:
    for key in ("media", "media_ids", "image", "images", "attachment", "url", "link"):
        if params.get(key):
            raise RuntimeError(f"{key} is not supported for text-only v1 posts")


def validate_x_post(params: dict[str, Any]) -> dict[str, str]:
    reject_media_fields(params)
    text = require_nonempty(params.get("text") or params.get("body") or "", "text")
    if len(text) > X_MAX_CHARS:
        raise RuntimeError(f"X posts must be at most {X_MAX_CHARS} characters (got {len(text)})")
    return {"text": text}


def normalize_subreddit(value: Any) -> str:
    name = clean_text(value).lstrip("/")
    if name.lower().startswith("r/"):
        name = name[2:]
    name = name.strip().strip("/")
    if not name:
        raise RuntimeError("subreddit is required")
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise RuntimeError(f"Invalid subreddit name: {name}")
    return name


def validate_reddit_post(params: dict[str, Any]) -> dict[str, str]:
    reject_media_fields(params)
    if params.get("url") or params.get("link"):
        raise RuntimeError("Link posts are not supported in v1; use a text (self) post")
    subreddit = normalize_subreddit(params.get("subreddit") or params.get("sr") or "")
    title = require_nonempty(params.get("title") or "", "title")
    if len(title) > REDDIT_TITLE_MAX:
        raise RuntimeError(
            f"Reddit titles must be at most {REDDIT_TITLE_MAX} characters (got {len(title)})"
        )
    text = require_nonempty(params.get("text") or params.get("body") or "", "text")
    return {"subreddit": subreddit, "title": title, "text": text}


def validate_linkedin_post(params: dict[str, Any]) -> dict[str, str]:
    reject_media_fields(params)
    if params.get("organization") or str(params.get("author_urn") or "").startswith(
        "urn:li:organization:"
    ):
        raise RuntimeError("LinkedIn company page posts are not supported in v1")
    text = require_nonempty(params.get("text") or params.get("body") or "", "text")
    if len(text) > LINKEDIN_MAX_CHARS:
        raise RuntimeError(
            f"LinkedIn posts must be at most {LINKEDIN_MAX_CHARS} characters (got {len(text)})"
        )
    return {"text": text}


def require_pending_draft(draft: dict[str, Any] | None, platform: str) -> dict[str, Any]:
    if not draft:
        raise RuntimeError(
            f"No pending {platform} draft. Create a draft first, then ask the user to approve before posting."
        )
    return draft
