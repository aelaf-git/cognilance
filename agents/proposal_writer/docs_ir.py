"""Convert proposal/report IR into Google Docs text requests + deferred inserts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProposalTable(BaseModel):
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class ChartSpec(BaseModel):
    chart_type: Literal["bar", "line", "pie"] = "bar"
    title: str = Field(default="", description="Chart title drawn on the image")
    labels: list[str] = Field(default_factory=list, description="Category / x-axis labels")
    values: list[float] = Field(default_factory=list, description="Numeric series values")
    series_name: str = Field(default="", description="Optional legend / y-axis label")


class ImageRef(BaseModel):
    url: str | None = Field(default=None, description="HTTP(S) image URL to insert (no generation)")
    drive_file_id: str | None = Field(
        default=None, description="Existing Drive file id to insert"
    )
    width_pt: float = Field(default=400, description="Inline image width in points")
    caption: str = Field(default="", description="Optional caption paragraph after the image")


class ProposalSection(BaseModel):
    heading: str
    level: Literal[1, 2, 3] = Field(
        default=1, description="Heading depth: 1=H1, 2=H2, 3=H3"
    )
    body: str = Field(
        default="",
        description="Section prose. Blank lines between paragraphs. '- ' lines for bullets.",
    )
    table: ProposalTable | None = None
    chart: ChartSpec | None = None
    image: ImageRef | None = None
    page_break_before: bool = False


class ProposalDraft(BaseModel):
    title: str = Field(description="Document title shown at the top of the Google Doc")
    subtitle: str = Field(default="", description="Optional client / engagement subtitle")
    client: str = Field(default="", description="Client or recipient organization if known")
    tone: str = Field(default="professional")
    sections: list[ProposalSection] = Field(
        default_factory=list,
        description="Ordered sections (exec summary, scope, pricing, findings, etc.)",
    )
    closing: str = Field(
        default="",
        description="Optional closing / next-steps paragraph after sections",
    )
    format_notes: str = Field(
        default="",
        description="Brief note on layout choices (tables, charts, fonts)",
    )
    document_id: str | None = Field(
        default=None,
        description="Existing Google Doc id when revising",
    )


NamedStyle = Literal[
    "TITLE",
    "SUBTITLE",
    "HEADING_1",
    "HEADING_2",
    "HEADING_3",
    "NORMAL_TEXT",
]

DeferredKind = Literal["table", "chart", "image"]


class DeferredInsert(BaseModel):
    kind: DeferredKind
    after_heading: str = ""
    table: ProposalTable | None = None
    chart: ChartSpec | None = None
    image: ImageRef | None = None


def _paragraph_chunks(text: str) -> list[tuple[str, bool]]:
    """Return (text, is_bullet) chunks from a section body."""
    chunks: list[tuple[str, bool]] = []
    buf: list[str] = []
    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "• ")):
            if buf:
                chunks.append(("\n".join(buf).strip(), False))
                buf = []
            chunks.append((stripped[2:].strip(), True))
        elif not stripped:
            if buf:
                chunks.append(("\n".join(buf).strip(), False))
                buf = []
        else:
            buf.append(line)
    if buf:
        chunks.append(("\n".join(buf).strip(), False))
    return [(t, b) for t, b in chunks if t]


def _insert_styled_paragraph(
    requests: list[dict[str, Any]],
    *,
    index: int,
    text: str,
    named_style: NamedStyle = "NORMAL_TEXT",
    bold: bool = False,
    font_family: str = "Georgia",
    font_size: float | None = None,
    bullet: bool = False,
) -> int:
    """Append Docs requests for one paragraph ending with newline. Return new index."""
    if not text.endswith("\n"):
        text = text + "\n"
    start = index
    end = index + len(text)
    requests.append({"insertText": {"location": {"index": index}, "text": text}})
    style: dict[str, Any] = {"namedStyleType": named_style}
    fields = ["namedStyleType"]
    if named_style == "TITLE":
        style["alignment"] = "CENTER"
        style["spaceBelow"] = {"magnitude": 6, "unit": "PT"}
        fields.extend(["alignment", "spaceBelow"])
    elif named_style == "SUBTITLE":
        style["alignment"] = "CENTER"
        style["spaceBelow"] = {"magnitude": 18, "unit": "PT"}
        fields.extend(["alignment", "spaceBelow"])
    elif named_style.startswith("HEADING"):
        style["spaceAbove"] = {"magnitude": 16, "unit": "PT"}
        style["spaceBelow"] = {"magnitude": 8, "unit": "PT"}
        fields.extend(["spaceAbove", "spaceBelow"])
    else:
        style["spaceBelow"] = {"magnitude": 8, "unit": "PT"}
        fields.append("spaceBelow")

    requests.append(
        {
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": style,
                "fields": ",".join(fields),
            }
        }
    )

    text_style: dict[str, Any] = {
        "weightedFontFamily": {"fontFamily": font_family},
    }
    text_fields = ["weightedFontFamily"]
    if bold or named_style in {"TITLE", "HEADING_1", "HEADING_2", "HEADING_3"}:
        text_style["bold"] = True
        text_fields.append("bold")
    if font_size is not None:
        text_style["fontSize"] = {"magnitude": float(font_size), "unit": "PT"}
        text_fields.append("fontSize")
    elif named_style == "TITLE":
        text_style["fontSize"] = {"magnitude": 22, "unit": "PT"}
        text_fields.append("fontSize")
    elif named_style == "SUBTITLE":
        text_style["fontSize"] = {"magnitude": 12, "unit": "PT"}
        text_fields.append("fontSize")
    elif named_style == "HEADING_1":
        text_style["fontSize"] = {"magnitude": 14, "unit": "PT"}
        text_fields.append("fontSize")
    elif named_style == "HEADING_2":
        text_style["fontSize"] = {"magnitude": 12, "unit": "PT"}
        text_fields.append("fontSize")
    elif named_style == "HEADING_3":
        text_style["fontSize"] = {"magnitude": 11, "unit": "PT"}
        text_fields.append("fontSize")

    content_end = end - 1 if text.endswith("\n") else end
    if content_end > start:
        requests.append(
            {
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": content_end},
                    "textStyle": text_style,
                    "fields": ",".join(text_fields),
                }
            }
        )

    if bullet:
        requests.append(
            {
                "createParagraphBullets": {
                    "range": {"startIndex": start, "endIndex": end},
                    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                }
            }
        )
    return end


def _heading_style(level: int) -> NamedStyle:
    if level >= 3:
        return "HEADING_3"
    if level == 2:
        return "HEADING_2"
    return "HEADING_1"


def draft_to_batch_requests(draft: ProposalDraft) -> tuple[list[dict[str, Any]], list[DeferredInsert]]:
    """Build text/style Docs requests and a list of native table/chart/image inserts.

    Tables, charts, and images are deferred so the executor can insert real Docs
    tables and inline images after the text body is written.
    """
    requests: list[dict[str, Any]] = []
    deferred: list[DeferredInsert] = []
    index = 1

    index = _insert_styled_paragraph(
        requests,
        index=index,
        text=draft.title.strip() or "Untitled Document",
        named_style="TITLE",
        font_family="Georgia",
    )
    subtitle = (draft.subtitle or "").strip()
    if not subtitle and draft.client.strip():
        subtitle = f"Prepared for {draft.client.strip()}"
    if subtitle:
        index = _insert_styled_paragraph(
            requests,
            index=index,
            text=subtitle,
            named_style="SUBTITLE",
            font_family="Georgia",
        )

    for section in draft.sections:
        if section.page_break_before:
            requests.append({"insertPageBreak": {"location": {"index": index}}})
            index += 1

        heading = (section.heading or "").strip() or "Section"
        index = _insert_styled_paragraph(
            requests,
            index=index,
            text=heading,
            named_style=_heading_style(int(section.level or 1)),
            font_family="Georgia",
        )
        for chunk, is_bullet in _paragraph_chunks(sanitize_body_text(section.body)):
            index = _insert_styled_paragraph(
                requests,
                index=index,
                text=chunk,
                named_style="NORMAL_TEXT",
                font_family="Georgia",
                font_size=11,
                bullet=is_bullet,
            )

        if section.table and (section.table.headers or section.table.rows):
            deferred.append(
                DeferredInsert(kind="table", after_heading=heading, table=section.table)
            )
        if section.chart and section.chart.labels and section.chart.values:
            deferred.append(
                DeferredInsert(kind="chart", after_heading=heading, chart=section.chart)
            )
        if section.image and (section.image.url or section.image.drive_file_id):
            deferred.append(
                DeferredInsert(kind="image", after_heading=heading, image=section.image)
            )

    closing = (draft.closing or "").strip()
    if closing:
        index = _insert_styled_paragraph(
            requests,
            index=index,
            text="Next Steps",
            named_style="HEADING_1",
            font_family="Georgia",
        )
        for chunk, is_bullet in _paragraph_chunks(closing):
            index = _insert_styled_paragraph(
                requests,
                index=index,
                text=chunk,
                named_style="NORMAL_TEXT",
                font_family="Georgia",
                font_size=11,
                bullet=is_bullet,
            )

    return requests, deferred


def clear_body_requests(end_index: int) -> list[dict[str, Any]]:
    """Build deleteContentRange requests that clear deletable body content.

    Google Docs always keeps a trailing segment newline that must not be deleted.
    ``end_index`` from the API is the body's exclusive end (past that newline), so
    a valid clear uses ``endIndex = end_index - 1``. Empty docs (only the newline)
    have ``end_index <= 2`` and need no delete.
    """
    if end_index <= 2:
        return []
    return [
        {
            "deleteContentRange": {
                "range": {"startIndex": 1, "endIndex": end_index - 1}
            }
        }
    ]


def sanitize_body_text(text: str) -> str:
    """Strip markdown so Docs insertText never receives ## / ** / * lists."""
    import re

    lines_out: list[str] = []
    in_fence = False
    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            lines_out.append(line)
            continue
        # Drop ATX headings — section titles are Docs named styles, not markdown.
        if re.match(r"^#{1,6}\s+", stripped):
            stripped = re.sub(r"^#{1,6}\s+", "", stripped)
            line = stripped
        # Convert markdown bullets to "- "
        if re.match(r"^(\*|\+|•)\s+", stripped):
            stripped = "- " + re.sub(r"^(\*|\+|•)\s+", "", stripped)
            line = stripped
        # Strip bold/italic markers
        stripped = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
        stripped = re.sub(r"__([^_]+)__", r"\1", stripped)
        stripped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", stripped)
        stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
        # Drop markdown table separator rows
        if re.match(r"^\|?\s*:?-{3,}", stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            stripped = " — ".join(c for c in cells if c)
            line = stripped
        else:
            line = stripped
        lines_out.append(line)
    # Collapse excessive blank lines
    cleaned: list[str] = []
    blank = 0
    for line in lines_out:
        if not line.strip():
            blank += 1
            if blank <= 1:
                cleaned.append("")
            continue
        blank = 0
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def body_text_requests(body: str, *, index: int) -> list[dict[str, Any]]:
    """Insert sanitized section body paragraphs/bullets at index (no heading)."""
    requests: list[dict[str, Any]] = []
    insert_at = index
    clean = sanitize_body_text(body)
    if not clean:
        return requests
    for chunk, is_bullet in _paragraph_chunks(clean):
        insert_at = _insert_styled_paragraph(
            requests,
            index=insert_at,
            text=chunk,
            named_style="NORMAL_TEXT",
            font_family="Georgia",
            font_size=11,
            bullet=is_bullet,
        )
    return requests


def delete_range_requests(start_index: int, end_index: int) -> list[dict[str, Any]]:
    """Delete [start, end) if the range is non-empty and valid for Docs."""
    if end_index <= start_index:
        return []
    return [
        {
            "deleteContentRange": {
                "range": {"startIndex": start_index, "endIndex": end_index}
            }
        }
    ]


def section_text_requests(section: ProposalSection, *, index: int) -> tuple[list[dict[str, Any]], int]:
    """Build heading + body text requests starting at index. Return (requests, new_index)."""
    requests: list[dict[str, Any]] = []
    insert_at = index
    if section.page_break_before:
        requests.append({"insertPageBreak": {"location": {"index": insert_at}}})
        insert_at += 1
    heading = (section.heading or "").strip() or "Section"
    insert_at = _insert_styled_paragraph(
        requests,
        index=insert_at,
        text=heading,
        named_style=_heading_style(int(section.level or 1)),
        font_family="Georgia",
    )
    body = sanitize_body_text(section.body)
    for chunk, is_bullet in _paragraph_chunks(body):
        insert_at = _insert_styled_paragraph(
            requests,
            index=insert_at,
            text=chunk,
            named_style="NORMAL_TEXT",
            font_family="Georgia",
            font_size=11,
            bullet=is_bullet,
        )
    return requests, insert_at


def section_deferred(section: ProposalSection) -> list[DeferredInsert]:
    heading = (section.heading or "").strip() or "Section"
    out: list[DeferredInsert] = []
    if section.table and (section.table.headers or section.table.rows):
        out.append(DeferredInsert(kind="table", after_heading=heading, table=section.table))
    if section.chart and section.chart.labels and section.chart.values:
        out.append(DeferredInsert(kind="chart", after_heading=heading, chart=section.chart))
    if section.image and (section.image.url or section.image.drive_file_id):
        out.append(DeferredInsert(kind="image", after_heading=heading, image=section.image))
    return out


def closing_text_requests(closing: str, *, index: int) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    insert_at = index
    insert_at = _insert_styled_paragraph(
        requests,
        index=insert_at,
        text="Next Steps",
        named_style="HEADING_1",
        font_family="Georgia",
    )
    body = sanitize_body_text(closing)
    for chunk, is_bullet in _paragraph_chunks(body):
        insert_at = _insert_styled_paragraph(
            requests,
            index=insert_at,
            text=chunk,
            named_style="NORMAL_TEXT",
            font_family="Georgia",
            font_size=11,
            bullet=is_bullet,
        )
    return requests
