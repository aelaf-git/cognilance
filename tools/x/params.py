"""Parameter preparation and validation for X posts."""

from __future__ import annotations

import re
from typing import Any

from core.context.drafts.store import DraftStore
from tools.social.validate import require_pending_draft, validate_x_post

DRAFT_KIND = "x_post"
_QUOTE_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'|“([^”]+)”')


def _extract_text(instruction: str, params: dict[str, Any]) -> dict[str, Any]:
    merged = dict(params)
    if not merged.get("text") and not merged.get("body"):
        for match in _QUOTE_RE.finditer(instruction or ""):
            quoted = next((g for g in match.groups() if g), None)
            if quoted and len(quoted.strip()) > 0:
                merged["text"] = quoted.strip()
                break
        if not merged.get("text"):
            # Strip common command prefixes
            text = re.sub(
                r"^(draft|post|publish|tweet|write)\s+(an?\s+)?(x\s+|twitter\s+)?(post|tweet)?\s*(about|saying|:)?\s*",
                "",
                (instruction or "").strip(),
                flags=re.IGNORECASE,
            ).strip()
            if text:
                merged["text"] = text
    return merged


def prepare_draft(
    instruction: str,
    params: dict[str, Any],
    *,
    conversation_id: str,
) -> dict[str, Any]:
    validated = validate_x_post(_extract_text(instruction, params))
    DraftStore().save_draft(conversation_id, DRAFT_KIND, validated)
    return validated


def prepare_post_params(
    instruction: str,
    params: dict[str, Any],
    *,
    conversation_id: str,
) -> dict[str, Any]:
    store = DraftStore()
    draft = require_pending_draft(store.get_pending(conversation_id, DRAFT_KIND), "X")
    # Allow explicit overrides only if they still validate; prefer saved draft.
    merged = {**draft, **{k: v for k, v in params.items() if v}}
    if instruction and any(
        w in instruction.lower() for w in ("post it", "publish", "tweet it", "send it")
    ):
        merged = draft
    return validate_x_post(merged)


def format_draft(draft: dict[str, Any]) -> str:
    text = str(draft.get("text") or "")
    return (
        "X draft ready for review:\n\n"
        f"{text}\n\n"
        f"({len(text)}/280 characters)\n\n"
        "Reply to approve and publish (e.g. “post it”), or ask for edits."
    )


def format_post_result(result: dict[str, Any]) -> str:
    url = result.get("url")
    post_id = result.get("post_id")
    if url:
        return f"Published to X: {url}"
    if post_id:
        return f"Published to X (id: {post_id})."
    return "Published to X."


def mark_draft_sent(conversation_id: str) -> None:
    if conversation_id:
        DraftStore().mark_sent(conversation_id, DRAFT_KIND)
