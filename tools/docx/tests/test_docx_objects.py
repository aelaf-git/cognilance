"""Charts, notes, links, and the other objects a Word file can hold."""

from __future__ import annotations

import json
import zipfile

import pytest

from core.context.request import current_conversation_id
from tools.docx import tool


def _package_xml(path) -> str:
    with zipfile.ZipFile(path) as archive:
        chunks = []
        for name in archive.namelist():
            if name.endswith((".xml", ".rels")):
                chunks.append(archive.read(name).decode("utf-8"))
        return "\n".join(chunks)


def _named(path, prefix: str) -> str:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.startswith(prefix)]
        return "\n".join(archive.read(name).decode("utf-8") for name in names)


@pytest.mark.asyncio
async def test_word_objects_are_in_the_file_and_survive_a_read(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-objects")
    try:
        created = await tool.run(
            "create",
            instruction=json.dumps(
                {
                    "title": "Hawking",
                    "style": {
                        "header": "Hawking",
                        "footer": "Biography",
                        "page_numbers": True,
                    },
                    "blocks": [
                        {"type": "heading", "level": 1, "text": "Early life"},
                        {
                            "type": "paragraph",
                            "runs": [
                                {
                                    "text": "See the paper",
                                    "link": "https://example.com",
                                    "note": "The page that states the date.",
                                }
                            ],
                        },
                        {
                            "type": "quote",
                            "text": "The universe keeps its secrets.",
                            "source": "Hawking",
                        },
                        {"type": "callout", "kind": "note", "text": "Check the citation."},
                        {
                            "type": "table",
                            "caption": "Table 1. Years",
                            "rows": [["Year", "Event"], ["1942", "Born"]],
                        },
                        {
                            "type": "chart",
                            "chart": "column",
                            "title": "Papers by quarter",
                            "caption": "Figure 1. Papers",
                            "categories": ["Q1", "Q2"],
                            "series": [{"name": "Revenue", "values": [2, 5]}],
                        },
                        {"type": "page_break"},
                    ],
                }
            ),
            params={},
            ctx=make_ctx("docx.create"),
        )
        path = tmp_path / f"{created.data['document_id']}.docx"
        chart = _named(path, "word/charts/chart1.xml")
        assert "Q1" in chart
        assert "Q2" in chart
        assert "Revenue" in chart
        package = _package_xml(path)
        assert "footnoteReference" in package
        assert "The page that states the date." in package
        assert "https://example.com" in package
        assert 'w:type="page"' in package
        assert "Hawking" in _named(path, "word/header")
        footer = _named(path, "word/footer")
        assert "Biography" in footer
        assert "PAGE" in footer

        read_back = await tool.run("read", instruction="{}", params={}, ctx=make_ctx("docx.read"))
        blocks = read_back.data["blocks"]
        assert any(block.get("text") == "The universe keeps its secrets." for block in blocks)
        assert any(block.get("text") == "Check the citation." for block in blocks)
        assert any(block.get("caption") == "Table 1. Years" for block in blocks)
        chart_block = next(block for block in blocks if block.get("type") == "chart")
        assert chart_block["title"] == "Papers by quarter"
        assert chart_block["series"][0]["name"] == "Revenue"

        with pytest.raises(RuntimeError, match="left unchanged"):
            await tool.run(
                "write",
                instruction=json.dumps(
                    {
                        "mode": "replace",
                        "blocks": [{"type": "paragraph", "text": "Only a new section."}],
                    }
                ),
                params={},
                ctx=make_ctx("docx.write"),
            )
        kept = await tool.run("read", instruction="{}", params={}, ctx=make_ctx("docx.read"))
        assert kept.data["version"] == 1
        assert any(block.get("type") == "chart" for block in kept.data["blocks"])
        assert any(block.get("title") == "Papers by quarter" for block in kept.data["blocks"])
    finally:
        current_conversation_id.reset(token)
