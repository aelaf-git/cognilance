"""Parameter preparation and validation for Reddit posts."""

from __future__ import annotations

import re
from typing import Any

from core.context.drafts.store import DraftStore
from tools.social.validate import require_pending_draft, validate_reddit_post

DRAFT_KIND = "reddit_post"
_SUB_RE = re.compile(r"(?:^|\s)r/([A-Za-z0-9_]+)", re.IGNORECASE)
_TITLE_RE = re.compile(r"title\s*:\s*(.+)", re.IGNORECASE)


def _extract_fields(instruction: str, params: dict[str, Any]) -> dict[str, Any]:
    merged = dict(params)
    text = instruction or ""
    if not merged.get("subreddit"):
        match = _SUB_RE.search(text)
        if match:
            merged["subreddit"] = match.group(1)
    if not merged.get("title"):
        match = _TITLE_RE.search(text)
        if match:
            merged["title"] = match.group(1).strip()
    if not merged.get("text") and not merged.get("body"):
        # Use remaining instruction after stripping known markers as body fallback
        body = text
        body = _SUB_RE.sub(" ", body)
        body = _TITLE_RE.sub(" ", body)
        body = re.sub(
            r"^(draft|post|publish|submit)\s+(a\s+)?(reddit\s+)?(post)?\s*(to\s+\S+)?\s*",
            "",
            body.strip(),
            flags=re.IGNORECASE,
        ).strip()
        if body and not merged.get("title"):
            # First line as title, rest as body when possible
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            if len(lines) >= 2:
                merged.setdefault("title", lines[0][:300])
                merged["text"] = "\n".join(lines[1:])
            elif lines:
                merged["text"] = lines[0]
        elif body:
            merged["text"] = body
    return merged


def prepare_draft(
    instruction: str,
    params: dict[str, Any],
    *,
    conversation_id: str,
) -> dict[str, Any]:
    validated = validate_reddit_post(_extract_fields(instruction, params))
    DraftStore().save_draft(conversation_id, DRAFT_KIND, validated)
    return validated


def prepare_post_params(
    instruction: str,
    params: dict[str, Any],
    *,
    conversation_id: str,
) -> dict[str, Any]:
    store = DraftStore()
    draft = require_pending_draft(store.get_pending(conversation_id, DRAFT_KIND), "Reddit")
    if instruction and any(
        w in instruction.lower() for w in ("post it", "publish", "submit it", "send it")
    ):
        return validate_reddit_post(draft)
    merged = {**draft, **{k: v for k, v in params.items() if v}}
    return validate_reddit_post(merged)


def format_draft(draft: dict[str, Any]) -> str:
    return (
        "Reddit draft ready for review:\n\n"
        f"Subreddit: r/{draft.get('subreddit')}\n"
        f"Title: {draft.get('title')}\n\n"
        f"{draft.get('text')}\n\n"
        "Reply to approve and submit (e.g. “post it”), or ask for edits."
    )


def format_post_result(result: dict[str, Any]) -> str:
    url = result.get("url")
    if url:
        return f"Submitted to Reddit: {url}"
    post_id = result.get("post_id")
    if post_id:
        return f"Submitted to Reddit (id: {post_id})."
    return "Submitted to Reddit."


def mark_draft_sent(conversation_id: str) -> None:
    if conversation_id:
        DraftStore().mark_sent(conversation_id, DRAFT_KIND)
