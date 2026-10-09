"""Parse Google Docs body_content into headed section ranges for surgical edits."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


_HEADING_STYLES = frozenset({"HEADING_1", "HEADING_2", "HEADING_3", "TITLE", "SUBTITLE"})

# Docs API alignment values.
ALIGNMENT_START = "START"
ALIGNMENT_CENTER = "CENTER"
ALIGNMENT_END = "END"
ALIGNMENT_JUSTIFIED = "JUSTIFIED"


@dataclass
class DocParagraph:
    start_index: int
    end_index: int
    text: str
    named_style: str
    is_bullet: bool = False
    alignment: str = ALIGNMENT_START


@dataclass
class DocSection:
    """A heading plus the body paragraphs until the next same-or-higher heading."""

    heading: str
    named_style: str
    heading_start: int
    heading_end: int
    body_start: int
    body_end: int
    body_text: str

    @property
    def has_body(self) -> bool:
        return self.body_end > self.body_start


def normalize_alignment(value: str | None) -> str:
    """Normalize Docs / user alignment strings to API enum values."""
    raw = (value or "").strip().upper()
    if not raw:
        return ALIGNMENT_START
    aliases = {
        "START": ALIGNMENT_START,
        "LEFT": ALIGNMENT_START,
        "CENTER": ALIGNMENT_CENTER,
        "CENTRE": ALIGNMENT_CENTER,
        "END": ALIGNMENT_END,
        "RIGHT": ALIGNMENT_END,
        "JUSTIFIED": ALIGNMENT_JUSTIFIED,
        "JUSTIFY": ALIGNMENT_JUSTIFIED,
    }
    return aliases.get(raw, ALIGNMENT_START)


def _paragraph_text(paragraph: dict[str, Any]) -> str:
    parts: list[str] = []
    for elem in paragraph.get("elements") or []:
        run = elem.get("textRun")
        if run and run.get("content"):
            parts.append(str(run["content"]))
    return "".join(parts)


def parse_paragraphs(body_content: list[dict[str, Any]] | None) -> list[DocParagraph]:
    """Extract paragraph elements with indexes from Docs body.content."""
    out: list[DocParagraph] = []
    for element in body_content or []:
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        start = int(element.get("startIndex") or 0)
        end = int(element.get("endIndex") or start)
        if end <= start:
            continue
        para_style = paragraph.get("paragraphStyle") or {}
        style = para_style.get("namedStyleType") or "NORMAL_TEXT"
        text = _paragraph_text(paragraph)
        is_bullet = bool(paragraph.get("bullet"))
        alignment = normalize_alignment(para_style.get("alignment"))
        out.append(
            DocParagraph(
                start_index=start,
                end_index=end,
                text=text,
                named_style=str(style),
                is_bullet=is_bullet,
                alignment=alignment,
            )
        )
    return out


def _heading_rank(named_style: str) -> int:
    if named_style == "TITLE":
        return 0
    if named_style == "SUBTITLE":
        return 1
    if named_style == "HEADING_1":
        return 2
    if named_style == "HEADING_2":
        return 3
    if named_style == "HEADING_3":
        return 4
    return 99


def parse_sections(body_content: list[dict[str, Any]] | None) -> list[DocSection]:
    """Split the document into heading-bounded sections (excludes TITLE/SUBTITLE as sections)."""
    paragraphs = parse_paragraphs(body_content)
    sections: list[DocSection] = []
    i = 0
    while i < len(paragraphs):
        para = paragraphs[i]
        style = para.named_style
        if style not in {"HEADING_1", "HEADING_2", "HEADING_3"}:
            i += 1
            continue
        heading = para.text.replace("\n", "").strip() or "Section"
        rank = _heading_rank(style)
        body_paras: list[DocParagraph] = []
        j = i + 1
        while j < len(paragraphs):
            nxt = paragraphs[j]
            if nxt.named_style in _HEADING_STYLES and _heading_rank(nxt.named_style) <= rank:
                break
            if nxt.named_style in {"HEADING_1", "HEADING_2", "HEADING_3"}:
                break
            body_paras.append(nxt)
            j += 1
        if body_paras:
            body_start = body_paras[0].start_index
            body_end = body_paras[-1].end_index
            body_bits: list[str] = []
            for bp in body_paras:
                line = bp.text.replace("\r", "").rstrip("\n")
                if bp.is_bullet:
                    line = line.lstrip()
                    if not line.startswith("- "):
                        line = f"- {line}"
                body_bits.append(line)
            body_text = "\n".join(body_bits).strip()
        else:
            body_start = para.end_index
            body_end = para.end_index
            body_text = ""
        sections.append(
            DocSection(
                heading=heading,
                named_style=style,
                heading_start=para.start_index,
                heading_end=para.end_index,
                body_start=body_start,
                body_end=body_end,
                body_text=body_text,
            )
        )
        i = j
    return sections


def paragraphs_in_section(
    paragraphs: list[DocParagraph],
    section: DocSection,
    *,
    include_heading: bool = True,
) -> list[DocParagraph]:
    """Return paragraphs that belong to a section (heading + body)."""
    start = section.heading_start if include_heading else section.body_start
    end = max(section.body_end, section.heading_end)
    return [p for p in paragraphs if p.start_index >= start and p.end_index <= end]


def alignment_summary(paragraphs: list[DocParagraph]) -> dict[str, int]:
    """Count paragraphs by normalized alignment."""
    counts: Counter[str] = Counter()
    for p in paragraphs:
        counts[normalize_alignment(p.alignment)] += 1
    return dict(counts)


def all_aligned(paragraphs: list[DocParagraph], target: str) -> bool:
    """True when every paragraph already has the target alignment."""
    if not paragraphs:
        return False
    want = normalize_alignment(target)
    return all(normalize_alignment(p.alignment) == want for p in paragraphs)


def coalesce_alignment_ranges(
    paragraphs: list[DocParagraph],
    target: str,
) -> list[tuple[int, int]]:
    """Build (start, end) ranges that need alignment updates (skip already matching)."""
    want = normalize_alignment(target)
    ranges: list[tuple[int, int]] = []
    for p in paragraphs:
        if normalize_alignment(p.alignment) == want:
            continue
        if ranges and ranges[-1][1] == p.start_index:
            ranges[-1] = (ranges[-1][0], p.end_index)
        else:
            ranges.append((p.start_index, p.end_index))
    return ranges


def alignment_update_requests(
    paragraphs: list[DocParagraph],
    target: str,
) -> list[dict[str, Any]]:
    """Docs batchUpdate requests to set paragraph alignment on mismatched ranges."""
    want = normalize_alignment(target)
    requests: list[dict[str, Any]] = []
    for start, end in coalesce_alignment_ranges(paragraphs, want):
        if end <= start:
            continue
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"alignment": want},
                    "fields": "alignment",
                }
            }
        )
    return requests


def _normalize_heading(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def find_section(
    sections: list[DocSection],
    query: str,
) -> DocSection | None:
    """Fuzzy-match a section by heading (exact, contains, or token overlap)."""
    q = _normalize_heading(query)
    if not q or not sections:
        return None
    for sec in sections:
        if _normalize_heading(sec.heading) == q:
            return sec
    for sec in sections:
        h = _normalize_heading(sec.heading)
        if q in h or h in q:
            return sec
    q_tokens = set(re.findall(r"[a-z0-9]+", q))
    best: DocSection | None = None
    best_score = 0
    for sec in sections:
        h_tokens = set(re.findall(r"[a-z0-9]+", _normalize_heading(sec.heading)))
        score = len(q_tokens & h_tokens)
        if score > best_score and score >= max(1, len(q_tokens) - 1):
            best = sec
            best_score = score
    return best


def sections_outline(sections: list[DocSection]) -> str:
    lines = []
    for i, sec in enumerate(sections, 1):
        preview = sec.body_text[:180].replace("\n", " ")
        lines.append(f"{i}. {sec.heading} ({sec.named_style})")
        if preview:
            lines.append(f"   Current body: {preview}{'…' if len(sec.body_text) > 180 else ''}")
        else:
            lines.append("   Current body: (empty)")
    return "\n".join(lines)
