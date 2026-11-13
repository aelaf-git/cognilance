"""Style, blocks, and tool-instruction parsing for local Word files."""

from __future__ import annotations

import json
import re
from typing import Any

from tools.docx.math import math_runs, normalize_math

DEFAULT_STYLE: dict[str, Any] = {
    "font_body": "Calibri",
    "font_heading": "Calibri",
    "body_size_pt": 11,
    "heading_size_pt": 16,
    "title_size_pt": 26,
    "alignment": "left",
    "margin_inches": 1.0,
    "page": "letter",
    "spacing_after_pt": 8,
    "line_spacing": 1.15,
    "header": "",
    "footer": "",
    "page_numbers": False,
    "orientation": "portrait",
    "columns": 1,
}

_CHARTS = {"column", "bar", "line", "pie", "area", "scatter"}
_CALLOUTS = {"note", "tip", "warning"}
_HIGHLIGHTS = {
    "yellow": "yellow",
    "green": "green",
    "cyan": "cyan",
    "magenta": "magenta",
    "blue": "blue",
    "red": "red",
    "darkblue": "darkBlue",
    "darkyellow": "darkYellow",
    "teal": "teal",
    "gray": "lightGray",
    "grey": "lightGray",
}

_STYLE_KEYS = set(DEFAULT_STYLE)
_FONT = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .'-]{0,39}")
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _font(value: Any, default: str) -> str:
    text = " ".join(str(value or "").split())
    if not _FONT.fullmatch(text):
        return default
    return text


def _number(value: Any, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(high, max(low, number))


def normalize_style(raw: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(DEFAULT_STYLE)
    if isinstance(raw, dict):
        source.update({key: value for key, value in raw.items() if key in _STYLE_KEYS})
    alignment = str(source.get("alignment") or "left").strip().lower()
    if alignment in {"centre", "middle"}:
        alignment = "center"
    if alignment in {"justified", "justify"}:
        alignment = "justify"
    if alignment not in {"left", "center", "justify"}:
        alignment = "left"
    page = str(source.get("page") or "letter").strip().lower().replace(" ", "")
    if page != "a4":
        page = "letter"
    orientation = str(source.get("orientation") or "portrait").strip().lower()
    if orientation not in {"portrait", "landscape"}:
        orientation = "portrait"
    return {
        "font_body": _font(source.get("font_body"), "Calibri"),
        "font_heading": _font(source.get("font_heading"), "Calibri"),
        "body_size_pt": _number(source.get("body_size_pt"), 11, 9, 18),
        "heading_size_pt": _number(source.get("heading_size_pt"), 16, 12, 28),
        "title_size_pt": _number(source.get("title_size_pt"), 26, 16, 36),
        "alignment": alignment,
        "margin_inches": _number(source.get("margin_inches"), 1.0, 0.5, 1.5),
        "page": page,
        "spacing_after_pt": _number(source.get("spacing_after_pt"), 8, 0, 24),
        "line_spacing": _number(source.get("line_spacing"), 1.15, 1.0, 2.0),
        "header": str(source.get("header") or "").strip()[:200],
        "footer": str(source.get("footer") or "").strip()[:200],
        "page_numbers": _flag(source.get("page_numbers")),
        "orientation": orientation,
        "columns": int(_number(source.get("columns"), 1, 1, 3)),
    }


def _flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _plain(value: Any) -> str:
    return normalize_math(str(value or "").strip())


def _items(value: Any) -> list[str]:
    if isinstance(value, str):
        return [line for line in (_plain(line) for line in value.splitlines()) if line]
    if isinstance(value, list):
        return [line for line in (_plain(item) for item in value) if line]
    return []


def _hex(value: Any) -> str:
    text = str(value or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{3}", text):
        text = "".join(char * 2 for char in text)
    if re.fullmatch(r"[0-9A-Fa-f]{6}", text):
        return text.upper()
    return ""


def _highlight(value: Any) -> str:
    return _HIGHLIGHTS.get(str(value or "").strip().lower().replace(" ", ""), "")


def _link(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith(("http://", "https://", "mailto:")):
        return text
    return ""


def _runs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    runs: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            text = _plain(item)
            if text:
                runs.append({"text": text})
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        note = _plain(item.get("note"))
        if not text and not note:
            continue
        run: dict[str, Any] = {"text": text}
        script = str(item.get("script") or "")
        if script in {"sub", "super"}:
            run["script"] = script
        if item.get("bold"):
            run["bold"] = True
        if item.get("italic"):
            run["italic"] = True
        if item.get("underline"):
            run["underline"] = True
        color = _hex(item.get("color"))
        if color:
            run["color"] = color
        highlight = _highlight(item.get("highlight"))
        if highlight:
            run["highlight"] = highlight
        link = _link(item.get("link") or item.get("url"))
        if link:
            run["link"] = link
        if note:
            run["note"] = note
        runs.append(run)
    return runs


def _cell(value: Any) -> Any:
    if isinstance(value, dict):
        runs = _runs(value.get("runs"))
        joined = "".join(str(run.get("text") or "") for run in runs)
        text = joined or _plain(value.get("text"))
        if not text and not runs:
            return ""
        if not runs and not value.get("note"):
            return text
        cell: dict[str, Any] = {"text": text}
        if runs:
            cell["runs"] = runs
        note = _plain(value.get("note"))
        if note:
            cell["note"] = note
        return cell
    return _plain(value)


def _rows(value: Any) -> list[list[Any]]:
    if not isinstance(value, list):
        return []
    rows: list[list[Any]] = []
    width = 0
    for raw_row in value:
        if isinstance(raw_row, list):
            cells = [_cell(cell) for cell in raw_row]
        elif isinstance(raw_row, str):
            cells = [_plain(part) for part in raw_row.split("|")]
        else:
            continue
        if any(cells):
            rows.append(cells)
            width = max(width, len(cells))
    return [row + [""] * (width - len(row)) for row in rows]


def _number_value(value: Any) -> int | float:
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def _chart(item: dict[str, Any]) -> dict[str, Any] | None:
    kind = str(item.get("chart") or item.get("kind") or "column").strip().lower()
    if kind not in _CHARTS:
        kind = "column"
    categories = [_plain(category) for category in item.get("categories") or [] if _plain(category)]
    series: list[dict[str, Any]] = []
    for raw in item.get("series") or []:
        if not isinstance(raw, dict):
            continue
        values: list[int | float] = []
        for value in raw.get("values") or []:
            try:
                values.append(_number_value(value))
            except (TypeError, ValueError):
                values.append(0)
        if not values:
            continue
        if categories and kind != "scatter":
            if len(values) < len(categories):
                values = [*values, *([0] * (len(categories) - len(values)))]
            else:
                values = values[: len(categories)]
        series.append({"name": _plain(raw.get("name")) or "Series", "values": values})
    if not categories or not series:
        return None
    block: dict[str, Any] = {
        "type": "chart",
        "chart": kind,
        "title": _plain(item.get("title") or item.get("text")),
        "categories": categories,
        "series": series,
    }
    caption = _plain(item.get("caption"))
    if caption:
        block["caption"] = caption
    return block


def _joined(item: dict[str, Any]) -> str:
    text = _plain(item.get("text"))
    if text:
        return text
    return "".join(str(run.get("text") or "") for run in _runs(item.get("runs")))


def _raw_text(item: dict[str, Any]) -> str:
    raw = item.get("text")
    if isinstance(raw, str) and raw.strip():
        return raw
    parts: list[str] = []
    for run in item.get("runs") or []:
        if isinstance(run, str):
            parts.append(run)
        elif isinstance(run, dict):
            parts.append(str(run.get("text") or ""))
    return "".join(parts)


def _expand_run(run: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(run.get("text") or "")
    if run.get("script") in {"sub", "super"} and not any(mark in text for mark in "\\^_"):
        return [run]
    pieces = math_runs(text)
    if len(pieces) == 1 and not pieces[0].get("script"):
        updated = dict(run)
        updated["text"] = pieces[0]["text"]
        return [updated]
    expanded: list[dict[str, Any]] = []
    for piece in pieces:
        nxt = {key: value for key, value in run.items() if key != "script"}
        nxt["text"] = piece["text"]
        script = piece.get("script") or (run.get("script") if run.get("script") in {"sub", "super"} else "")
        if script:
            nxt["script"] = script
        expanded.append(nxt)
    return expanded


def _attach_math(block: dict[str, Any], source: str = "") -> dict[str, Any]:
    if block.get("runs"):
        expanded: list[dict[str, Any]] = []
        for run in block["runs"]:
            expanded.extend(_expand_run(run))
        block["runs"] = [run for run in expanded if run.get("text") or run.get("note")]
        if block["runs"]:
            block["text"] = "".join(str(run.get("text") or "") for run in block["runs"])
        return block
    pieces = math_runs(source or str(block.get("text") or ""))
    if any(piece.get("script") for piece in pieces):
        block["runs"] = pieces
    if pieces:
        block["text"] = "".join(piece["text"] for piece in pieces)
    return block


def _with_runs(block: dict[str, Any], item: dict[str, Any], text: str) -> dict[str, Any]:
    raw = _raw_text(item) or text
    runs = _runs(item.get("runs"))
    if runs:
        text = "".join(str(run.get("text") or "") for run in runs)
        block["runs"] = runs
    if text:
        block["text"] = text
    note = _plain(item.get("note"))
    if note:
        block["note"] = note
    return _attach_math(block, raw)


def normalize_blocks(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str) and raw.strip():
        return [_attach_math({"type": "paragraph", "text": raw}, raw)]
    if not isinstance(raw, list):
        return []
    blocks: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            blocks.append(_attach_math({"type": "paragraph", "text": item}, item))
            continue
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "paragraph").strip().lower()
        if kind in {"rule", "hr", "line"}:
            blocks.append({"type": "rule"})
            continue
        if kind in {"page_break", "pagebreak", "break"}:
            blocks.append({"type": "page_break"})
            continue
        if kind in {"contents", "toc"}:
            blocks.append({"type": "contents"})
            continue
        if kind in {"bullet", "bullets", "list", "numbered", "number"}:
            items = _items(item.get("items") if item.get("items") is not None else item.get("text"))
            if items:
                blocks.append({
                    "type": "numbered" if kind in {"numbered", "number"} else "bullet",
                    "items": items,
                })
            continue
        if kind in {"references", "bibliography", "reference"}:
            items = _items(item.get("items") if item.get("items") is not None else item.get("text"))
            if items:
                blocks.append({"type": "references", "items": items})
            continue
        if kind == "table":
            rows = _rows(item.get("rows"))
            if rows:
                block = {"type": "table", "rows": rows, "header": bool(item.get("header", True))}
                caption = _plain(item.get("caption"))
                if caption:
                    block["caption"] = caption
                blocks.append(block)
            continue
        if kind == "chart":
            chart = _chart(item)
            if chart:
                blocks.append(chart)
            continue
        if kind == "code":
            text = str(item.get("text") or "").strip()
            if text:
                block = {"type": "code", "text": text}
                language = str(item.get("language") or "").strip()[:40]
                if language:
                    block["language"] = language
                blocks.append(block)
            continue
        if kind == "callout":
            text = _joined(item)
            if text:
                callout = str(item.get("kind") or item.get("callout") or "note").strip().lower()
                block = _with_runs(
                    {"type": "callout", "kind": callout if callout in _CALLOUTS else "note"},
                    item,
                    text,
                )
                blocks.append(block)
            continue
        if kind in {"quote", "blockquote"}:
            text = _joined(item)
            if text:
                block = _with_runs({"type": "quote"}, item, text)
                source = _plain(item.get("source"))
                if source:
                    block["source"] = source
                blocks.append(block)
            continue
        if kind == "equation":
            text = _joined(item)
            if text:
                blocks.append(_with_runs({"type": "equation"}, item, text))
            continue
        text = _joined(item)
        if not text and not _plain(item.get("note")):
            continue
        if kind == "title":
            blocks.append(_with_runs({"type": "title"}, item, text))
        elif kind in {"heading", "header"}:
            level = int(_number(item.get("level"), 1, 1, 3))
            blocks.append(_with_runs({"type": "heading", "level": level}, item, text))
        else:
            blocks.append(_with_runs({"type": "paragraph"}, item, text))
    return blocks


def _relax_json(raw: str) -> str:
    """Keep LaTeX commands that JSON would treat as escapes.

    ``\\nu`` and ``\\frac`` stay commands. A real ``\\n`` before a quote or
    space, ``\\"``, ``\\\\``, ``\\/``, and ``\\u`` plus four hex digits stay
    JSON escapes.
    """
    out: list[str] = []
    index = 0
    length = len(raw)
    while index < length:
        if raw[index] != "\\":
            out.append(raw[index])
            index += 1
            continue
        nxt = raw[index + 1] if index + 1 < length else ""
        if nxt == "\\":
            out.append("\\\\")
            index += 2
            continue
        if nxt == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", raw[index + 2 : index + 6]):
            out.append(raw[index : index + 6])
            index += 6
            continue
        if nxt in {'"', "/"}:
            out.append(raw[index : index + 2])
            index += 2
            continue
        if nxt in "bfnrt":
            after = raw[index + 2] if index + 2 < length else ""
            if after.isalpha():
                out.append("\\\\")
                out.append(nxt)
                index += 2
                continue
            out.append(raw[index : index + 2])
            index += 2
            continue
        out.append("\\\\")
        index += 1
    return "".join(out)


def _loads_object(candidate: str) -> dict[str, Any] | None:
    relaxed = _relax_json(candidate)
    attempts = (relaxed, candidate) if relaxed != candidate else (candidate,)
    for attempt in attempts:
        try:
            value = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    fence = _JSON_FENCE.search(text)
    candidate = fence.group(1) if fence else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidate = text[start : end + 1]
    if not candidate:
        return None
    return _loads_object(candidate)


def parse_payload(instruction: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Params win over a JSON object embedded in the instruction string."""
    merged = dict(_extract_json(instruction) or {})
    for key, value in dict(params or {}).items():
        if value not in (None, "", [], {}):
            merged[key] = value
    text = (instruction or "").strip()
    if text and not text.startswith("{") and "```" not in text:
        merged.setdefault("text", text)
    return merged


def style_patch(payload: dict[str, Any]) -> dict[str, Any]:
    """Only the style fields the caller set. Missing fields stay as they are."""
    style: dict[str, Any] = {}
    raw = payload.get("style") if isinstance(payload.get("style"), dict) else {}
    for key in _STYLE_KEYS:
        if key in raw:
            style[key] = raw[key]
        elif key in payload:
            style[key] = payload[key]
    return style


def style_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return normalize_style(style_patch(payload))


def blocks_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("blocks") is not None:
        return normalize_blocks(payload.get("blocks"))
    for key in ("content", "body", "text"):
        if payload.get(key):
            return normalize_blocks(payload.get(key))
    return []


def title_from_payload(payload: dict[str, Any], blocks: list[dict[str, Any]]) -> str:
    title = _plain(payload.get("title"))
    if title:
        return title[:200]
    for block in blocks:
        if block.get("type") in {"title", "heading"} and block.get("text"):
            return str(block["text"])[:200]
    return "Document"
