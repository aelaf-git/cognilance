"""Local Word files: render, restyle, and edit the conversation's active file."""

from __future__ import annotations

import json
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.docx import router
from core.context.request import current_conversation_id
from tools.docx import tool
from tools.registry import tool_risk


def test_manifest_grades():
    assert tool_risk("docx.create") == "draft"
    assert tool_risk("docx.write") == "reversible_write"
    assert tool_risk("docx.style") == "reversible_write"
    assert tool_risk("docx.read") == "read"


def _zip_xml(path, name: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name).decode("utf-8")


def _styles_xml(path) -> str:
    return _zip_xml(path, "word/styles.xml")


@pytest.mark.asyncio
async def test_create_write_style_and_active_file(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-docx")
    ctx = make_ctx("docx.create")
    try:
        created = await tool.run(
            "create",
            instruction=json.dumps(
                {
                    "title": "Market brief",
                    "style": {
                        "font_body": "Calibri",
                        "font_heading": "Georgia",
                        "body_size_pt": 11,
                        "heading_size_pt": 18,
                    },
                    "blocks": [
                        {"type": "heading", "text": "Market", "level": 1},
                        {"type": "paragraph", "text": "The first paragraph."},
                        {"type": "bullet", "items": ["Teams", "Agents"]},
                    ],
                }
            ),
            params={},
            ctx=ctx,
        )
        document_id = created.data["document_id"]
        docx_path = tmp_path / f"{document_id}.docx"
        assert docx_path.is_file()
        assert docx_path.read_bytes()[:2] == b"PK"
        styles = _styles_xml(docx_path)
        assert "Georgia" in styles
        assert "Calibri" in styles

        read_back = await tool.run(
            "read",
            instruction="{}",
            params={},
            ctx=make_ctx("docx.read"),
        )
        assert read_back.data["document_id"] == document_id
        texts = [block.get("text") for block in read_back.data["blocks"]]
        assert "The first paragraph." in texts

        updated = await tool.run(
            "write",
            instruction=json.dumps(
                {
                    "mode": "append",
                    "blocks": [{"type": "paragraph", "text": "A second paragraph."}],
                }
            ),
            params={},
            ctx=make_ctx("docx.write"),
        )
        assert updated.data["document_id"] == document_id
        assert updated.data["version"] == 2
        written = [block.get("text") for block in updated.data["blocks"]]
        assert "The first paragraph." in written
        assert "A second paragraph." in written

        restyled = await tool.run(
            "style",
            instruction=json.dumps({"style": {"font_body": "Garamond", "font_heading": "Garamond"}}),
            params={},
            ctx=make_ctx("docx.style"),
        )
        assert restyled.data["document_id"] == document_id
        assert restyled.data["style"]["font_body"] == "Garamond"
        assert restyled.data["style"]["font_heading"] == "Garamond"
        assert restyled.data["style"]["heading_size_pt"] == 18
        assert "Garamond" in _styles_xml(docx_path)
        assert ctx.client.calls == []
    finally:
        current_conversation_id.reset(token)


@pytest.mark.asyncio
async def test_other_conversation_does_not_edit_the_open_file(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-a")
    try:
        created = await tool.run(
            "create",
            instruction=json.dumps({"title": "Notes", "blocks": [{"type": "paragraph", "text": "Keep this."}]}),
            params={},
            ctx=make_ctx("docx.create"),
        )
        document_id = created.data["document_id"]
        other = current_conversation_id.set("conv-b")
        try:
            with pytest.raises(RuntimeError, match="No Word file"):
                await tool.run(
                    "write",
                    instruction=json.dumps({"mode": "append", "blocks": [{"type": "paragraph", "text": "Nope."}]}),
                    params={},
                    ctx=make_ctx("docx.write"),
                )
        finally:
            current_conversation_id.reset(other)
        read_back = await tool.run(
            "read",
            instruction=json.dumps({"document_id": document_id}),
            params={},
            ctx=make_ctx("docx.read"),
        )
        assert [block.get("text") for block in read_back.data["blocks"]] == ["Keep this."]
    finally:
        current_conversation_id.reset(token)


@pytest.mark.asyncio
async def test_download_route_returns_the_docx(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-download")
    try:
        created = await tool.run(
            "create",
            instruction=json.dumps({"title": "Export me", "blocks": [{"type": "paragraph", "text": "Body"}]}),
            params={},
            ctx=make_ctx("docx.create"),
        )
    finally:
        current_conversation_id.reset(token)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    document_id = created.data["document_id"]
    response = client.get(f"/docx/{document_id}/file")
    assert response.status_code == 200
    assert response.content[:2] == b"PK"
    assert "attachment" in response.headers["content-disposition"]
    missing = client.get("/docx/not-a-real-id/file")
    assert missing.status_code == 404


def test_equations_become_characters():
    from tools.docx.math import normalize_math

    assert normalize_math(r"E=mc^2") == "E=mc\u00b2"
    assert normalize_math(r"H_2O") == "H\u2082O"
    assert normalize_math(r"\alpha") == "\u03b1"
    assert normalize_math(r"\leq") == "\u2264"
    assert normalize_math(r"\frac{1}{2}") == "\u00b9\u2044\u2082"
    assert normalize_math(r"x^{n+1}") == "x\u207f\u207a\u00b9"


@pytest.mark.asyncio
async def test_partial_write_keeps_the_open_file(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-keep")
    try:
        await tool.run(
            "create",
            instruction=json.dumps(
                {
                    "title": "Biography",
                    "blocks": [
                        {"type": "paragraph", "text": "The first paragraph."},
                        {"type": "paragraph", "text": "The second paragraph."},
                        {"type": "paragraph", "text": "The third paragraph."},
                    ],
                }
            ),
            params={},
            ctx=make_ctx("docx.create"),
        )
        original = ["The first paragraph.", "The second paragraph.", "The third paragraph."]

        async def read_back():
            return await tool.run(
                "read",
                instruction="{}",
                params={},
                ctx=make_ctx("docx.read"),
            )

        with pytest.raises(RuntimeError, match="left unchanged"):
            await tool.run(
                "write",
                instruction=json.dumps(
                    {"mode": "replace", "blocks": [{"type": "paragraph", "text": "Only a new section."}]}
                ),
                params={},
                ctx=make_ctx("docx.write"),
            )
        with pytest.raises(RuntimeError, match="left unchanged"):
            await tool.run(
                "write",
                instruction="Please add a section about the prizes.",
                params={},
                ctx=make_ctx("docx.write"),
            )
        with pytest.raises(RuntimeError, match="left unchanged"):
            await tool.run(
                "write",
                instruction=json.dumps({"mode": "append", "blocks": []}),
                params={},
                ctx=make_ctx("docx.write"),
            )
        kept = await read_back()
        assert [block.get("text") for block in kept.data["blocks"]] == original
        assert kept.data["version"] == 1

        inserted = await tool.run(
            "write",
            instruction=json.dumps(
                {
                    "mode": "insert",
                    "at": 1,
                    "blocks": [{"type": "heading", "level": 2, "text": "Later life"}],
                }
            ),
            params={},
            ctx=make_ctx("docx.write"),
        )
        assert [block.get("text") for block in inserted.data["blocks"]] == [
            "The first paragraph.",
            "Later life",
            "The second paragraph.",
            "The third paragraph.",
        ]

        replaced = await tool.run(
            "write",
            instruction=json.dumps(
                {
                    "mode": "replace_block",
                    "index": 2,
                    "blocks": [{"type": "paragraph", "text": "The second paragraph, expanded."}],
                }
            ),
            params={},
            ctx=make_ctx("docx.write"),
        )
        assert [block.get("text") for block in replaced.data["blocks"]] == [
            "The first paragraph.",
            "Later life",
            "The second paragraph, expanded.",
            "The third paragraph.",
        ]
    finally:
        current_conversation_id.reset(token)


@pytest.mark.asyncio
async def test_formula_is_saved_with_superscript_and_subscript(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-math")
    try:
        created = await tool.run(
            "create",
            instruction=json.dumps(
                {
                    "title": "Formulas",
                    "blocks": [
                        {
                            "type": "paragraph",
                            "text": r"E=mc^2 and H_2O and \alpha and \frac{1}{2}",
                        }
                    ],
                }
            ),
            params={},
            ctx=make_ctx("docx.create"),
        )
        text = created.data["blocks"][0]["text"]
        assert "E=mc\u00b2" in text
        assert "H\u2082O" in text
        assert "\u03b1" in text
        assert "\u00b9\u2044\u2082" in text
        xml = _zip_xml(tmp_path / f"{created.data['document_id']}.docx", "word/document.xml")
        assert "superscript" in xml
        assert "subscript" in xml
        assert "\u03b1" in xml
        assert "Cambria Math" in xml
    finally:
        current_conversation_id.reset(token)
