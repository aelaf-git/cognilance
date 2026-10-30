"""Render a stored document record to a .docx file."""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor

from tools.docx.chart import chart_xml
from tools.docx.math import split_runs

_MATH_FONT = "Cambria Math"
_CODE_FONT = "Consolas"
_CALLOUT_FILL = {"note": "D6E6F5", "tip": "D9EAD3", "warning": "FCE4D6"}
_HEADER_FILL = "D9E2F3"

_ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _set_rfonts(element: Any, name: str, *, math: bool = False) -> None:
    r_pr = element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    scripts = ("w:ascii", "w:hAnsi", "w:cs") if math else ("w:ascii", "w:hAnsi")
    for attr in scripts:
        r_fonts.set(qn(attr), name)


def _style_font(style: Any, name: str, size_pt: float) -> None:
    style.font.name = name
    style.font.size = Pt(size_pt)
    _set_rfonts(style.element, name)


def _run(
    paragraph: Any,
    text: str,
    name: str,
    size_pt: float,
    *,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    color: str = "",
    highlight: str = "",
    align: str | None = None,
    math: bool = False,
) -> Any:
    run = paragraph.add_run(text)
    run.bold = bold or None
    run.italic = italic or None
    run.underline = underline or None
    run.font.name = name
    run.font.size = Pt(size_pt)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    _set_rfonts(run._element, name, math=math)
    r_pr = run._element.get_or_add_rPr()
    if align:
        vert = OxmlElement("w:vertAlign")
        vert.set(qn("w:val"), align)
        r_pr.append(vert)
    if highlight:
        mark = OxmlElement("w:highlight")
        mark.set(qn("w:val"), highlight)
        r_pr.append(mark)
    if text.startswith(" ") or text.endswith(" "):
        text_elm = run._element.find(qn("w:t"))
        if text_elm is not None:
            text_elm.set(qn("xml:space"), "preserve")
    return run


def _write_text(
    paragraph: Any,
    text: str,
    name: str,
    size_pt: float,
    *,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    color: str = "",
    highlight: str = "",
    link: str = "",
    document: Any = None,
    literal: bool = False,
) -> None:
    runs = [("plain", text)] if literal else split_runs(text)
    if not runs:
        _run(paragraph, "", name, size_pt, bold=bold, italic=italic, underline=underline)
        return
    created = []
    for kind, chunk in runs:
        if kind == "super":
            created.append(
                _run(
                    paragraph,
                    chunk,
                    _MATH_FONT,
                    size_pt,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    color=color,
                    highlight=highlight,
                    align="superscript",
                    math=True,
                )
            )
        elif kind == "sub":
            created.append(
                _run(
                    paragraph,
                    chunk,
                    _MATH_FONT,
                    size_pt,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    color=color,
                    highlight=highlight,
                    align="subscript",
                    math=True,
                )
            )
        elif kind == "math":
            created.append(
                _run(
                    paragraph,
                    chunk,
                    _MATH_FONT,
                    size_pt,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    color=color,
                    highlight=highlight,
                    math=True,
                )
            )
        else:
            created.append(
                _run(
                    paragraph,
                    chunk,
                    name,
                    size_pt,
                    bold=bold,
                    italic=italic,
                    underline=underline,
                    color=color,
                    highlight=highlight,
                )
            )
    if link and document is not None and created:
        rel = document.part.relate_to(link, RT.HYPERLINK, is_external=True)
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), rel)
        for run in created:
            element = run._r
            element.getparent().remove(element)
            hyperlink.append(element)
        paragraph._p.append(hyperlink)


def _write_content(paragraph: Any, block: dict[str, Any], document: Any, notes: list[str], name: str, size_pt: float, *, bold: bool = False, italic: bool = False) -> None:
    runs = list(block.get("runs") or [])
    if runs:
        for run in runs:
            _write_text(
                paragraph,
                str(run.get("text") or ""),
                name,
                size_pt,
                bold=bold or bool(run.get("bold")),
                italic=italic or bool(run.get("italic")),
                underline=bool(run.get("underline")),
                color=str(run.get("color") or ""),
                highlight=str(run.get("highlight") or ""),
                link=str(run.get("link") or ""),
                document=document,
            )
            if run.get("note"):
                _footnote(paragraph, notes, str(run["note"]))
    else:
        _write_text(
            paragraph,
            str(block.get("text") or ""),
            name,
            size_pt,
            bold=bold,
            italic=italic,
            document=document,
        )
    if block.get("note"):
        _footnote(paragraph, notes, str(block["note"]))


def _footnote(paragraph: Any, notes: list[str], text: str) -> None:
    notes.append(text)
    run = paragraph.add_run()
    r_pr = run._element.get_or_add_rPr()
    vert = OxmlElement("w:vertAlign")
    vert.set(qn("w:val"), "superscript")
    r_pr.append(vert)
    ref = OxmlElement("w:footnoteReference")
    ref.set(qn("w:id"), str(len(notes)))
    run._element.append(ref)


def _paragraph_format(paragraph: Any, style: dict[str, Any], *, alignment: str | None = None) -> None:
    chosen = alignment or str(style.get("alignment") or "left")
    paragraph.alignment = _ALIGN.get(chosen, WD_ALIGN_PARAGRAPH.LEFT)
    paragraph.paragraph_format.space_after = Pt(float(style["spacing_after_pt"]))
    paragraph.paragraph_format.line_spacing = float(style["line_spacing"])


def _heading_size(style: dict[str, Any], level: int) -> float:
    base = float(style["heading_size_pt"])
    if level <= 1:
        return base
    if level == 2:
        return max(12, base * 0.85)
    return max(12, base * 0.75)


def _shade(element: Any, fill: str) -> None:
    props = element.get_or_add_pPr() if element.tag == qn("w:p") else element.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), fill)
    props.append(shading)


def _bottom_rule(paragraph: Any) -> None:
    props = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "666666")
    borders.append(bottom)
    props.append(borders)


def _page_field(paragraph: Any) -> None:
    begin = paragraph.add_run()
    start = OxmlElement("w:fldChar")
    start.set(qn("w:fldCharType"), "begin")
    begin._r.append(start)
    instruction = paragraph.add_run()
    text = OxmlElement("w:instrText")
    text.set(qn("xml:space"), "preserve")
    text.text = " PAGE "
    instruction._r.append(text)
    end = paragraph.add_run()
    stop = OxmlElement("w:fldChar")
    stop.set(qn("w:fldCharType"), "end")
    end._r.append(stop)


def _contents_field(paragraph: Any) -> None:
    begin = paragraph.add_run()
    start = OxmlElement("w:fldChar")
    start.set(qn("w:fldCharType"), "begin")
    begin._r.append(start)
    instruction = paragraph.add_run()
    text = OxmlElement("w:instrText")
    text.set(qn("xml:space"), "preserve")
    text.text = ' TOC \\o "1-3" \\h \\z \\u '
    instruction._r.append(text)
    end = paragraph.add_run()
    stop = OxmlElement("w:fldChar")
    stop.set(qn("w:fldCharType"), "end")
    end._r.append(stop)


def _caption(document: Any, style: dict[str, Any], text: str) -> None:
    paragraph = document.add_paragraph()
    _paragraph_format(paragraph, style)
    _write_text(paragraph, text, style["font_body"], max(9, float(style["body_size_pt"]) - 1), italic=True)


def _cell_block(cell: Any) -> dict[str, Any]:
    if isinstance(cell, dict):
        return cell
    return {"text": str(cell or "")}


def _add_chart(document: Any, block: dict[str, Any], index: int) -> None:
    part = Part(
        PackURI(f"/word/charts/chart{index}.xml"),
        CT.DML_CHART,
        chart_xml(block).encode("utf-8"),
        document.part.package,
    )
    rel = document.part.relate_to(part, RT.CHART)
    paragraph = document.add_paragraph()
    drawing = parse_xml(
        '<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<w:drawing><wp:inline>"
        '<wp:extent cx="5486400" cy="3200400"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{1000 + index}" name="Chart {index}"/>'
        "<wp:cNvGraphicFramePr/>"
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
        f'<c:chart r:id="{rel}"/>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>"
    )
    paragraph._p.append(drawing)


def _save_footnotes(document: Any, notes: list[str]) -> None:
    if not notes:
        return
    items = [
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>',
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>',
    ]
    for index, note in enumerate(notes, 1):
        items.append(
            f'<w:footnote w:id="{index}"><w:p>'
            '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>'
            f"<w:r><w:t xml:space=\"preserve\"> {escape(note)}</w:t></w:r>"
            "</w:p></w:footnote>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        + "".join(items)
        + "</w:footnotes>"
    )
    part = Part(
        PackURI("/word/footnotes.xml"),
        CT.WML_FOOTNOTES,
        xml.encode("utf-8"),
        document.part.package,
    )
    document.part.relate_to(part, RT.FOOTNOTES)


def _apply_section(document: Any, style: dict[str, Any]) -> None:
    section = document.sections[0]
    if style.get("page") == "a4":
        section.page_width = Mm(210)
        section.page_height = Mm(297)
    else:
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
    if style.get("orientation") == "landscape":
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width
    margin = Inches(float(style["margin_inches"]))
    section.left_margin = margin
    section.right_margin = margin
    section.top_margin = margin
    section.bottom_margin = margin
    columns = int(style.get("columns") or 1)
    if columns > 1:
        cols = OxmlElement("w:cols")
        cols.set(qn("w:num"), str(columns))
        cols.set(qn("w:space"), "720")
        section._sectPr.append(cols)
    header = str(style.get("header") or "").strip()
    footer = str(style.get("footer") or "").strip()
    if header:
        story = section.header
        story.is_linked_to_previous = False
        paragraph = story.paragraphs[0]
        paragraph.clear()
        _write_text(paragraph, header, style["font_body"], float(style["body_size_pt"]))
    if footer or style.get("page_numbers"):
        story = section.footer
        story.is_linked_to_previous = False
        paragraph = story.paragraphs[0]
        paragraph.clear()
        if footer:
            _write_text(paragraph, footer, style["font_body"], float(style["body_size_pt"]))
        if style.get("page_numbers"):
            if footer:
                paragraph.add_run(" ")
            _page_field(paragraph)


def render_docx(path: Any, record: dict[str, Any]) -> None:
    style = record["style"]
    document = Document()
    _apply_section(document, style)
    notes: list[str] = []
    charts = 0

    _style_font(document.styles["Normal"], style["font_body"], float(style["body_size_pt"]))
    _style_font(document.styles["Title"], style["font_heading"], float(style["title_size_pt"]))
    _style_font(document.styles["Heading 1"], style["font_heading"], _heading_size(style, 1))
    _style_font(document.styles["Heading 2"], style["font_heading"], _heading_size(style, 2))
    _style_font(document.styles["Heading 3"], style["font_heading"], _heading_size(style, 3))
    available = {item.name for item in document.styles}
    for list_style in ("List Bullet", "List Number"):
        if list_style in available:
            _style_font(document.styles[list_style], style["font_body"], float(style["body_size_pt"]))

    blocks = list(record.get("blocks") or [])
    if not any(block.get("type") == "title" for block in blocks) and record.get("title"):
        blocks = [{"type": "title", "text": record["title"]}, *blocks]

    body = float(style["body_size_pt"])
    for block in blocks:
        kind = block.get("type")
        if kind == "title":
            paragraph = document.add_paragraph(style="Title")
            _paragraph_format(paragraph, style)
            _write_content(paragraph, block, document, notes, style["font_heading"], float(style["title_size_pt"]), bold=True)
        elif kind == "heading":
            level = int(block.get("level") or 1)
            paragraph = document.add_paragraph(style=f"Heading {level}")
            _paragraph_format(paragraph, style, alignment="left" if style["alignment"] != "center" else "center")
            _write_content(paragraph, block, document, notes, style["font_heading"], _heading_size(style, level), bold=True)
        elif kind in {"bullet", "numbered"}:
            style_name = "List Number" if kind == "numbered" else "List Bullet"
            for index, item in enumerate(block.get("items") or [], 1):
                if style_name in available:
                    paragraph = document.add_paragraph(style=style_name)
                    text = str(item)
                else:
                    paragraph = document.add_paragraph()
                    prefix = f"{index}. " if kind == "numbered" else "• "
                    text = prefix + str(item)
                _paragraph_format(paragraph, style)
                _write_text(paragraph, text, style["font_body"], body)
        elif kind == "quote":
            paragraph = document.add_paragraph()
            _paragraph_format(paragraph, style)
            paragraph.paragraph_format.left_indent = Inches(0.4)
            _write_content(paragraph, block, document, notes, style["font_body"], body, italic=True)
            source = str(block.get("source") or "").strip()
            if source:
                credit = document.add_paragraph()
                _paragraph_format(credit, style, alignment="right")
                _write_text(credit, source, style["font_body"], max(9, body - 1))
        elif kind == "code":
            language = str(block.get("language") or "").strip()
            if language:
                label = document.add_paragraph()
                _paragraph_format(label, style)
                _write_text(label, language, style["font_body"], 9, bold=True)
            paragraph = document.add_paragraph()
            _paragraph_format(paragraph, style, alignment="left")
            _shade(paragraph._p, "F3F4F6")
            lines = str(block.get("text") or "").split("\n")
            for index, line in enumerate(lines):
                if index:
                    paragraph.add_run()._r.append(OxmlElement("w:br"))
                _write_text(paragraph, line or " ", _CODE_FONT, 10, literal=True)
        elif kind == "callout":
            paragraph = document.add_paragraph()
            _paragraph_format(paragraph, style)
            _shade(paragraph._p, _CALLOUT_FILL.get(str(block.get("kind") or "note"), "D6E6F5"))
            _write_content(paragraph, block, document, notes, style["font_body"], body)
        elif kind == "equation":
            paragraph = document.add_paragraph()
            _paragraph_format(paragraph, style, alignment="center")
            _write_content(paragraph, block, document, notes, _MATH_FONT, body + 2)
        elif kind == "rule":
            paragraph = document.add_paragraph()
            _paragraph_format(paragraph, style)
            _bottom_rule(paragraph)
        elif kind == "page_break":
            document.add_page_break()
        elif kind == "contents":
            paragraph = document.add_paragraph()
            _paragraph_format(paragraph, style)
            _contents_field(paragraph)
        elif kind == "references":
            for item in block.get("items") or []:
                paragraph = document.add_paragraph()
                _paragraph_format(paragraph, style)
                paragraph.paragraph_format.left_indent = Inches(0.35)
                paragraph.paragraph_format.first_line_indent = Inches(-0.35)
                _write_text(paragraph, str(item), style["font_body"], body)
        elif kind == "table":
            rows = block.get("rows") or []
            if not rows:
                continue
            if block.get("caption"):
                _caption(document, style, str(block["caption"]))
            table = document.add_table(rows=len(rows), cols=len(rows[0]))
            table.style = "Table Grid"
            for row_index, row in enumerate(rows):
                for col_index, raw_cell in enumerate(row):
                    cell = table.rows[row_index].cells[col_index]
                    cell.text = ""
                    payload = _cell_block(raw_cell)
                    header = bool(block.get("header", True) and row_index == 0)
                    if header:
                        _shade(cell._tc, _HEADER_FILL)
                    _write_content(
                        cell.paragraphs[0],
                        payload,
                        document,
                        notes,
                        style["font_body"],
                        body,
                        bold=header,
                    )
            document.add_paragraph()
        elif kind == "chart":
            if block.get("caption"):
                _caption(document, style, str(block["caption"]))
            charts += 1
            _add_chart(document, block, charts)
        else:
            paragraph = document.add_paragraph()
            _paragraph_format(paragraph, style)
            _write_content(paragraph, block, document, notes, style["font_body"], body)

    _save_footnotes(document, notes)
    document.save(str(path))
