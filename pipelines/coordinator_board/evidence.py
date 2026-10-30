"""Evidence the judge, later steps, and grounding can actually check.

A list, or a dict of lists, keeps every item. Each item contributes its type,
length, opening words, and closing words. Payloads without that shape keep a
bounded dump that still includes the ending.
"""

from __future__ import annotations

import json
from typing import Any

_OPEN_WORDS = 16
_SNIPPET_CHARS = 80
_DUMP_CAP = 1600
_DUMP_EDGE = 700


def evidence_text(value: Any) -> str:
    rendered = _render(value).strip()
    return rendered or "{}"


def _render(value: Any) -> str:
    if isinstance(value, list):
        return _render_list(value)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines: list[str] = []
        for key, item in value.items():
            rendered = _render(item)
            if "\n" in rendered:
                lines.append(f"{key}:\n{rendered}")
            else:
                lines.append(f"{key}: {rendered}")
        return "\n".join(lines)
    if isinstance(value, str):
        return _bounded_text(value)
    return _bounded_text(json.dumps(value, default=str))


def _render_list(items: list[Any]) -> str:
    lines = [f"{len(items)} items"]
    lines.extend(_part_line(index, item) for index, item in enumerate(items))
    return "\n".join(lines)


def _part_line(index: int, item: Any) -> str:
    kind, length, text = _describe(item)
    opening, closing = _ends(text)
    return f"- [{index}] {kind} len={length} open={opening!r} close={closing!r}"


def _describe(item: Any) -> tuple[str, int, str]:
    if isinstance(item, str):
        return "str", len(item), item
    if isinstance(item, dict):
        kind = str(item.get("type") or item.get("kind") or "object")
        text = _item_text(item)
        return kind, len(text), text
    if isinstance(item, list):
        return "list", len(item), json.dumps(item, default=str)
    text = json.dumps(item, default=str)
    return type(item).__name__, len(text), text


def _item_text(item: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key, value in item.items():
        if key in {"type", "kind"}:
            continue
        if isinstance(value, str) and value.strip():
            chunks.append(value.strip())
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, str) and child.strip():
                    chunks.append(child.strip())
                elif isinstance(child, dict):
                    nested = _item_text(child)
                    if nested.strip():
                        chunks.append(nested.strip())
    if chunks:
        return " ".join(chunks)
    return json.dumps(item, default=str)


def _ends(text: str) -> tuple[str, str]:
    compact = " ".join(text.split())
    if not compact:
        return "", ""
    words = compact.split(" ")
    if len(words) <= _OPEN_WORDS * 2:
        return compact[:_SNIPPET_CHARS], compact[-_SNIPPET_CHARS:]
    opening = " ".join(words[:_OPEN_WORDS])[:_SNIPPET_CHARS]
    closing = " ".join(words[-_OPEN_WORDS:])[-_SNIPPET_CHARS:]
    return opening, closing


def _bounded_text(text: str) -> str:
    if len(text) <= _DUMP_CAP:
        return text
    return f"{text[:_DUMP_EDGE].rstrip()}\n…\n{text[-_DUMP_EDGE:].lstrip()}"
