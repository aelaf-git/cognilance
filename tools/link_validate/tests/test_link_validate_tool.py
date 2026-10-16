from tools.link_validate import extract_links
from tools.registry import tool_risk


def test_manifest():
    assert tool_risk("link_validate.check") == "read"
    assert tool_risk("link.validate") == "read"  # legacy alias


def test_extract_links_dedupes():
    text = "https://a.com, https://a.com and https://b.com."
    assert extract_links(text) == ["https://a.com", "https://b.com"]
