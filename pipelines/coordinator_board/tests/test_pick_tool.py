"""Regression: greetings must not force web.search."""

from core.context.request import current_conversation_id
from pipelines.coordinator_board.specialists import _pick_tool

_RESEARCHER_TOOLS = ("web.search", "link_validate.check", "thinking")
_DOCX_TOOLS = ("docx.create", "docx.write", "docx.style", "docx.read", "thinking")


def test_greeting_uses_thinking():
    for greeting in ("Hey", "Hello", "thanks", "ok"):
        assert _pick_tool("researcher", greeting, _RESEARCHER_TOOLS) == "thinking"


def test_research_query_uses_web_search():
    assert (
        _pick_tool(
            "researcher",
            "search the latest news on AI",
            _RESEARCHER_TOOLS,
        )
        == "web.search"
    )


def test_look_up_uses_web_search():
    assert (
        _pick_tool("researcher", "look up the capital of France", _RESEARCHER_TOOLS)
        == "web.search"
    )


def test_url_validation_uses_link_validate():
    assert (
        _pick_tool(
            "researcher",
            "please valid https://example.com",
            _RESEARCHER_TOOLS,
        )
        == "link_validate.check"
    )


def test_docx_agent_creates_when_no_file_is_open(monkeypatch):
    monkeypatch.setattr("tools.docx.store.active_document_id", lambda _conversation_id: None)
    token = current_conversation_id.set("conv-docx-new")
    try:
        assert _pick_tool("docx_agent", "write a one page brief titled Market", _DOCX_TOOLS) == "docx.create"
    finally:
        current_conversation_id.reset(token)


def test_docx_agent_styles_when_the_instruction_is_about_fonts(monkeypatch):
    monkeypatch.setattr("tools.docx.store.active_document_id", lambda _conversation_id: "doc_abcabcabcabc")
    token = current_conversation_id.set("conv-docx-style")
    try:
        assert _pick_tool("docx_agent", "change the font to Georgia", _DOCX_TOOLS) == "docx.style"
    finally:
        current_conversation_id.reset(token)


def test_docx_agent_writes_when_a_file_is_open(monkeypatch):
    monkeypatch.setattr("tools.docx.store.active_document_id", lambda _conversation_id: "doc_abcabcabcabc")
    token = current_conversation_id.set("conv-docx-edit")
    try:
        assert _pick_tool("docx_agent", "add a closing paragraph", _DOCX_TOOLS) == "docx.write"
    finally:
        current_conversation_id.reset(token)


def test_report_writer_does_not_open_a_word_file():
    assert _pick_tool("report_writer", "save this as a docx", ("google_docs.create", "thinking")) == "thinking"
