from tools.registry import tool_risk
from tools.web import extract_urls


def test_manifest():
    assert tool_risk("web.search") == "read"
    assert tool_risk("web.fetch") == "read"


def test_extract_urls():
    assert extract_urls("see https://example.com/a and http://b.org") == [
        "https://example.com/a",
        "http://b.org",
    ]
