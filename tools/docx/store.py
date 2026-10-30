"""Filesystem store for local Word files and the conversation's active file."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from core.context.db import ensure_db_dir
from tools.docx.math import normalize_math
from tools.docx.model import (
    blocks_from_payload,
    normalize_blocks,
    normalize_style,
    style_from_payload,
    style_patch,
    title_from_payload,
)
from tools.docx.render import render_docx

_ID = re.compile(r"^doc_[a-f0-9]{12}$")
DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def docx_root() -> Path:
    override = os.getenv("COGNILANCE_DOCX_DIR")
    root = Path(override) if override else ensure_db_dir().parent / "docx"
    root.mkdir(parents=True, exist_ok=True)
    return root


def valid_id(document_id: str) -> bool:
    return bool(_ID.fullmatch(document_id or ""))


def _active_path() -> Path:
    return docx_root() / "active.json"


def _read_active() -> dict[str, str]:
    path = _active_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if valid_id(str(value))}


def active_document_id(conversation_id: str) -> str | None:
    if not conversation_id:
        return None
    document_id = _read_active().get(conversation_id)
    if document_id and (docx_root() / f"{document_id}.json").is_file():
        return document_id
    return None


def set_active(conversation_id: str, document_id: str) -> None:
    if not conversation_id or not valid_id(document_id):
        return
    current = _read_active()
    current[conversation_id] = document_id
    path = _active_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(current))
    tmp.replace(path)


def _save(record: dict[str, Any]) -> None:
    root = docx_root()
    document_id = record["id"]
    json_final = root / f"{document_id}.json"
    docx_final = root / f"{document_id}.docx"
    json_tmp = root / f"{document_id}.json.tmp"
    docx_tmp = root / f"{document_id}.docx.tmp"
    render_docx(docx_tmp, record)
    json_tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    docx_tmp.replace(docx_final)
    json_tmp.replace(json_final)


def _load(document_id: str) -> dict[str, Any]:
    if not valid_id(document_id):
        raise RuntimeError("Unknown document id")
    path = docx_root() / f"{document_id}.json"
    if not path.is_file():
        raise RuntimeError("No Word file with that id")
    try:
        record = json.loads(path.read_text())
        if not record.get("id"):
            raise KeyError("id")
    except (OSError, json.JSONDecodeError, AttributeError, KeyError) as exc:
        raise RuntimeError("The Word file could not be read") from exc
    return record


def resolve_id(document_id: str | None, conversation_id: str) -> str:
    chosen = (document_id or "").strip()
    if chosen:
        if not valid_id(chosen):
            raise RuntimeError("Unknown document id")
        return chosen
    active = active_document_id(conversation_id)
    if not active:
        raise RuntimeError("No Word file is open for this conversation")
    return active


def create_document(payload: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    blocks = blocks_from_payload(payload)
    record = {
        "id": f"doc_{uuid.uuid4().hex[:12]}",
        "title": title_from_payload(payload, blocks),
        "version": 1,
        "style": style_from_payload(payload),
        "blocks": blocks,
        "conversation_id": conversation_id,
    }
    _save(record)
    set_active(conversation_id, record["id"])
    return record


def _unchanged(reason: str) -> RuntimeError:
    return RuntimeError(f"{reason} The open file was left unchanged.")


def _piece(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or "").strip()
    return str(value or "").strip()


def _block_texts(blocks: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for block in blocks:
        kind = block.get("type")
        if kind in {"bullet", "numbered", "references"}:
            texts.extend(piece for item in block.get("items") or [] if (piece := _piece(item)))
        elif kind == "table":
            caption = _piece(block.get("caption"))
            if caption:
                texts.append(caption)
            for row in block.get("rows") or []:
                texts.extend(piece for cell in row if (piece := _piece(cell)))
                texts.extend(
                    note
                    for cell in row
                    if isinstance(cell, dict) and (note := _piece(cell.get("note")))
                )
        elif kind == "chart":
            for key in ("title", "caption"):
                piece = _piece(block.get(key))
                if piece:
                    texts.append(piece)
        else:
            for key in ("text", "note", "source"):
                piece = _piece(block.get(key))
                if piece:
                    texts.append(piece)
    return texts


def _preserves(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> bool:
    haystack = "\n".join(normalize_math(piece) for piece in _block_texts(incoming))
    return all(normalize_math(piece) in haystack for piece in _block_texts(existing))


def _index(value: Any, size: int, *, allow_end: bool) -> int:
    if value is None or value == "":
        raise _unchanged("This edit needs an index.")
    try:
        index = int(value)
    except (TypeError, ValueError) as exc:
        raise _unchanged("This edit needs an index.") from exc
    if size == 0 and not allow_end:
        raise _unchanged("There is no block at that index.")
    limit = size if allow_end else size - 1
    if index < 0 or index > limit:
        raise _unchanged("There is no block at that index.")
    return index


def _blocks_for_write(payload: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    if payload.get("blocks") is not None:
        incoming = normalize_blocks(payload.get("blocks"))
    elif mode in {"replace_block", "replace-block"} and str(payload.get("text") or "").strip():
        incoming = normalize_blocks(
            [
                {
                    "type": payload.get("type") or "paragraph",
                    "text": payload.get("text"),
                    "level": payload.get("level"),
                    "items": payload.get("items"),
                }
            ]
        )
    else:
        incoming = []
    if not incoming:
        raise _unchanged("A write needs blocks.")
    return incoming


def write_document(payload: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    record = _load(resolve_id(str(payload.get("document_id") or ""), conversation_id))
    existing = list(record.get("blocks") or [])
    mode = str(payload.get("mode") or "replace").strip().lower()
    incoming = _blocks_for_write(payload, mode)
    if mode in {"append", "add"}:
        updated = existing + incoming
    elif mode == "insert":
        at = _index(payload.get("at"), len(existing), allow_end=True)
        updated = existing[:at] + incoming + existing[at:]
    elif mode in {"replace_block", "replace-block"}:
        index = _index(payload.get("index"), len(existing), allow_end=False)
        updated = existing[:index] + incoming + existing[index + 1 :]
    elif existing and not _preserves(existing, incoming):
        raise _unchanged(
            "That replace would drop existing text. Use append or insert, or include every current paragraph."
        )
    else:
        updated = incoming
    title = normalize_math(str(payload.get("title") or "").strip())
    if title:
        record["title"] = title[:200]
    record["version"] = int(record.get("version") or 1) + 1
    record["blocks"] = normalize_blocks(updated)
    _save(record)
    set_active(conversation_id, record["id"])
    return record


def style_document(payload: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    record = _load(resolve_id(str(payload.get("document_id") or ""), conversation_id))
    record["style"] = normalize_style({**dict(record.get("style") or {}), **style_patch(payload)})
    record["version"] = int(record.get("version") or 1) + 1
    _save(record)
    set_active(conversation_id, record["id"])
    return record


def read_document(payload: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    return _load(resolve_id(str(payload.get("document_id") or ""), conversation_id))


def export_file(document_id: str) -> tuple[Path, str]:
    record = _load(document_id)
    path = docx_root() / f"{record['id']}.docx"
    if not path.is_file():
        raise RuntimeError("The Word file is missing")
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "", str(record.get("title") or "document")).strip() or "document"
    return path, f"{cleaned[:80]}.docx"
