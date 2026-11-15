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
    saved = client.get(f"/docx/{document_id}")
    assert saved.status_code == 200
    assert saved.json()["title"] == "Export me"
    assert saved.json()["blocks"][0]["text"] == "Body"
    assert client.get("/docx/not-a-real-id").status_code == 404


def test_equations_become_characters():
    from tools.docx.math import math_runs, normalize_math
    from tools.docx.model import normalize_blocks

    assert normalize_math(r"E=mc^2") == "E=mc\u00b2"
    assert normalize_math(r"H_2O") == "H\u2082O"
    assert normalize_math(r"\alpha") == "\u03b1"
    assert normalize_math(r"\leq") == "\u2264"
    assert normalize_math(r"\frac{1}{2}") == "\u00b9\u2044\u2082"
    assert normalize_math(r"x^{n+1}") == "x\u207f\u207a\u00b9"
    field = r"G_{\mu\nu} + \Lambda g_{\mu\nu} = \frac{8\pi G}{c^{4}} T_{\mu\nu}"
    runs = math_runs(field)
    subscripts = [run["text"] for run in runs if run.get("script") == "sub"]
    assert subscripts.count("\u03bc\u03bd") == 3
    assert any("\u039b" in run["text"] and not run.get("script") for run in runs)
    assert any(run.get("script") == "super" and run["text"] == "\u03c0" for run in runs)
    assert normalize_math(r"G_\mu\nu") == "G\u03bc\u03bd"
    assert math_runs(r"G_\mu\nu")[1] == {"text": "\u03bc\u03bd", "script": "sub"}
    blocks = normalize_blocks(
        [
            {"type": "equation", "text": field},
            {"type": "paragraph", "text": r"Where G_\mu\nu is the tensor and \Lambda is the constant."},
        ]
    )
    assert blocks[0]["runs"][1]["script"] == "sub"
    assert any(run.get("script") == "sub" and "\u03bc" in run["text"] for run in blocks[1]["runs"])
    from tools.docx.model import parse_payload

    payload = parse_payload(
        r'{"blocks":[{"type":"equation","text":"G_{\mu\nu} + \Lambda g_{\mu\nu} = \frac{8\pi G}{c^{4}} T_{\mu\nu}"}]}',
        None,
    )
    written = normalize_blocks(payload["blocks"])
    assert written[0]["type"] == "equation"
    assert any(run.get("script") == "sub" and run["text"] == "\u03bc\u03bd" for run in written[0]["runs"])
    assert "\u039b" in written[0]["text"]


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


@pytest.mark.asyncio
async def test_write_without_mode_appends(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-append-default")
    try:
        await tool.run(
            "create",
            instruction=json.dumps({"title": "Notes", "blocks": [{"type": "paragraph", "text": "Keep this."}]}),
            params={},
            ctx=make_ctx("docx.create"),
        )
        updated = await tool.run(
            "write",
            instruction=json.dumps({"blocks": [{"type": "paragraph", "text": "Added."}]}),
            params={},
            ctx=make_ctx("docx.write"),
        )
        assert [block.get("text") for block in updated.data["blocks"]] == ["Keep this.", "Added."]
    finally:
        current_conversation_id.reset(token)


@pytest.mark.asyncio
async def test_structured_blocks_are_written(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-fields")
    try:
        await tool.run(
            "create",
            instruction=json.dumps({"title": "Notes", "blocks": [{"type": "paragraph", "text": "Keep this."}]}),
            params={},
            ctx=make_ctx("docx.create"),
        )
        updated = await tool.run(
            "write",
            instruction="",
            params={"blocks": [{"type": "paragraph", "text": "From fields."}]},
            ctx=make_ctx("docx.write"),
        )
        assert [block.get("text") for block in updated.data["blocks"]] == ["Keep this.", "From fields."]
    finally:
        current_conversation_id.reset(token)


@pytest.mark.asyncio
async def test_fraction_is_stored_as_office_math(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-omml")
    try:
        created = await tool.run(
            "create",
            instruction=json.dumps(
                {
                    "title": "Field equation",
                    "blocks": [
                        {
                            "type": "equation",
                            "text": r"G_{\mu\nu} = \frac{8\pi G}{c^{4}} T_{\mu\nu}",
                        }
                    ],
                }
            ),
            params={},
            ctx=make_ctx("docx.create"),
        )
        xml = _zip_xml(tmp_path / f"{created.data['document_id']}.docx", "word/document.xml")
        assert "oMath" in xml
        assert "m:f" in xml or ":f " in xml or "<m:f>" in xml
        assert created.data["blocks"][0]["notation"] == r"G_{\mu\nu} = \frac{8\pi G}{c^{4}} T_{\mu\nu}"
    finally:
        current_conversation_id.reset(token)


@pytest.mark.asyncio
async def test_block_ids_survive_replace_and_delete(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-block-ids")
    try:
        created = await tool.run(
            "create",
            instruction=json.dumps(
                {
                    "title": "Notes",
                    "blocks": [
                        {"type": "paragraph", "text": "Keep this."},
                        {"type": "paragraph", "text": "Change this."},
                        {"type": "paragraph", "text": "Leave this."},
                    ],
                }
            ),
            params={},
            ctx=make_ctx("docx.create"),
        )
        blocks = created.data["blocks"]
        assert all(str(block["id"]).startswith("blk_") for block in blocks)
        kept, target, other = (block["id"] for block in blocks)
        replaced = await tool.run(
            "write",
            instruction="",
            params={
                "mode": "replace_block",
                "block_id": target,
                "blocks": [{"type": "paragraph", "text": "Changed."}],
            },
            ctx=make_ctx("docx.write"),
        )
        assert [block["id"] for block in replaced.data["blocks"]] == [kept, target, other]
        assert [block["text"] for block in replaced.data["blocks"]] == ["Keep this.", "Changed.", "Leave this."]
        deleted = await tool.run(
            "write",
            instruction="",
            params={"mode": "delete", "block_id": target},
            ctx=make_ctx("docx.write"),
        )
        assert [block["id"] for block in deleted.data["blocks"]] == [kept, other]
        assert [block["text"] for block in deleted.data["blocks"]] == ["Keep this.", "Leave this."]
    finally:
        current_conversation_id.reset(token)


@pytest.mark.asyncio
async def test_grouped_subscript_keeps_notation(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-notation")
    try:
        created = await tool.run(
            "create",
            instruction=json.dumps(
                {"title": "Tensor", "blocks": [{"type": "equation", "text": r"G_{\mu\nu}"}]}
            ),
            params={},
            ctx=make_ctx("docx.create"),
        )
        assert created.data["blocks"][0]["notation"] == r"G_{\mu\nu}"
    finally:
        current_conversation_id.reset(token)


@pytest.mark.asyncio
async def test_restore_brings_back_the_previous_paragraph(tmp_path, monkeypatch, make_ctx):
    monkeypatch.setenv("COGNILANCE_DOCX_DIR", str(tmp_path))
    token = current_conversation_id.set("conv-restore")
    try:
        created = await tool.run(
            "create",
            instruction=json.dumps(
                {"title": "Draft", "blocks": [{"type": "paragraph", "text": "The first paragraph."}]}
            ),
            params={},
            ctx=make_ctx("docx.create"),
        )
        document_id = created.data["document_id"]
        await tool.run(
            "write",
            instruction=json.dumps({"blocks": [{"type": "paragraph", "text": "A later paragraph."}]}),
            params={},
            ctx=make_ctx("docx.write"),
        )
        from tools.docx.store import public_document, restore_previous

        restored = public_document(restore_previous(document_id)["id"])
        assert [block["text"] for block in restored["blocks"]] == ["The first paragraph."]
    finally:
        current_conversation_id.reset(token)
