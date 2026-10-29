"""Regression: greetings must not force web.search."""

from pipelines.coordinator_board.specialists import _pick_tool

_RESEARCHER_TOOLS = ("web.search", "link_validate.check", "thinking")


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
