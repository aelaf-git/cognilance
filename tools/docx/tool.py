"""Write and style local Word files. This tool never calls Google or the broker."""

from __future__ import annotations

from typing import Any

from core.context.request import current_conversation_id
from pipelines.shared.streaming import emit
from tools.docx.model import parse_payload
from tools.docx.store import create_document, read_document, style_document, write_document
from tools.registry import ToolContext, ToolOutput


def _public(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": record["id"],
        "id": record["id"],
        "title": record["title"],
        "version": record["version"],
        "style": record["style"],
        "blocks": record["blocks"],
    }


def _describe(record: dict[str, Any], action: str) -> str:
    title = record["title"]
    document_id = record["id"]
    style = record["style"]
    fonts = f'{style["font_heading"]} headings, {style["font_body"]} body'
    count = len(record.get("blocks") or [])
    if action == "create":
        lead = f'Created Word file "{title}" ({document_id}).'
    elif action == "write":
        lead = f'Updated Word file "{title}" ({document_id}).'
    elif action == "style":
        lead = f'Restyled Word file "{title}" ({document_id}).'
    else:
        lead = f'Word file "{title}" ({document_id}).'
    lines = [f"{lead} Style: {fonts}. Blocks: {count}."]
    if action == "read":
        for block in record.get("blocks") or []:
            kind = block.get("type")
            if kind in {"bullet", "numbered"}:
                lines.append(f"{kind}: " + "; ".join(block.get("items") or []))
            elif kind == "table":
                caption = block.get("caption") or ""
                lines.append(f"table: {caption} {len(block.get('rows') or [])} rows".strip())
            elif kind == "chart":
                lines.append(f"chart: {block.get('chart') or 'column'} {block.get('title') or ''}".strip())
            elif kind == "references":
                lines.append("references: " + "; ".join(block.get("items") or []))
            elif kind in {"rule", "page_break", "contents"}:
                lines.append(str(kind))
            else:
                note = f" note: {block['note']}" if block.get("note") else ""
                lines.append(f"{kind}: {block.get('text') or ''}{note}")
    return "\n".join(lines)


async def run(action: str, *, instruction: str, params: dict[str, Any], ctx: ToolContext) -> ToolOutput:
    del ctx
    payload = parse_payload(instruction, params)
    conversation_id = current_conversation_id.get() or ""
    if action == "create":
        record = create_document(payload, conversation_id)
    elif action == "write":
        record = write_document(payload, conversation_id)
    elif action == "style":
        record = style_document(payload, conversation_id)
    elif action == "read":
        record = read_document(payload, conversation_id)
    else:
        raise RuntimeError(f"Unknown docx action: {action}")
    if action != "read":
        public = _public(record)
        emit(
            "document",
            id=public["id"],
            title=public["title"],
            version=public["version"],
            style=public["style"],
            blocks=public["blocks"],
        )
    return ToolOutput(text=_describe(record, action), data=_public(record))
