"""Docs Creator Agent — empty titled Google Docs via orchestrator Docs proxy."""

from __future__ import annotations

import os
import re
from pathlib import Path

from cognilance import CognilanceWorker
from dotenv import load_dotenv

from proxy import OrchestratorProxyError, docs_create

_AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(_AGENT_DIR / ".env")

_TITLE_RE = re.compile(
    r"""(?:titled|title|named|called)\s+["“']?([^"'”\n]+)["”']?""",
    re.I,
)
_QUOTE_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'|“([^”]+)”')
_CREATE_PREFIX_RE = re.compile(
    r"^(please\s+)?(can you\s+)?(create|make|new|open)\s+"
    r"(me\s+)?(a\s+|an\s+)?(new\s+)?(blank\s+|empty\s+)?"
    r"(google\s+)?(document|doc)s?\s*",
    re.I,
)
_TRAILING_INTENT_RE = re.compile(
    r"\b(i will|i'll|i am going to|i'm going to|so i can|for me to).*$",
    re.I,
)


worker = CognilanceWorker(
    name="Docs Creator Agent",
    skills=["docs-creating"],
    description=(
        "Creates empty titled Google Docs via the orchestrator Docs proxy. "
        "Does not write body content — the user writes in the Doc."
    ),
    tags=["worker", "google-docs", "documents", "create"],
    port=8105,
)


def parse_doc_title(text: str) -> str:
    """Extract a document title; never invent story content."""
    raw = (text or "").strip()
    match = _TITLE_RE.search(raw)
    if match:
        return _clean_title(match.group(1))
    quoted = _QUOTE_RE.search(raw)
    if quoted:
        return _clean_title(next(g for g in quoted.groups() if g))
    stripped = _CREATE_PREFIX_RE.sub("", raw)
    title = _clean_title(stripped)
    return title or "Untitled"


def _clean_title(value: str) -> str:
    title = re.sub(r"\s+", " ", (value or "").strip())
    title = _TRAILING_INTENT_RE.sub("", title)
    if ". " in title:
        title = title.split(". ", 1)[0]
    title = title.strip(" .,:;-")
    title = re.sub(
        r"\b(google\s+)?(document|doc)s?\b",
        "",
        title,
        flags=re.I,
    )
    title = re.sub(r"\s+", " ", title).strip(" .,:;-")
    return title[:120]


@worker.on_task
async def handle(task):
    text = (task.input.text or "").strip()
    data = task.input.data or {}
    title = parse_doc_title(text)
    task.think(f'Creating empty Google Doc titled "{title}"')
    try:
        created = await docs_create(data, name=title, content="")
    except OrchestratorProxyError as exc:
        return task.fail(message=str(exc))
    document_id = str(created.get("document_id") or created.get("id") or "").strip()
    url = str(created.get("url") or "").strip()
    if document_id and not url:
        url = f"https://docs.google.com/document/d/{document_id}/edit"
    if not document_id:
        return task.fail(message="Google Doc was created but no document_id was returned")
    summary = f'Created empty Google Doc "{title}".'
    if url:
        summary += f"\nOpen: {url}"
    return task.complete(
        text=summary,
        data={
            "title": title,
            "name": title,
            "document_id": document_id,
            "url": url,
            "status": "created",
            "content_written": False,
        },
    )


if __name__ == "__main__":
    os.chdir(_AGENT_DIR)
    worker.run()
