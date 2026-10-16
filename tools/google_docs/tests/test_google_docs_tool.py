import pytest

from tools.conftest import FakeClient
from tools.google_docs import tool
from tools.registry import tool_risk


def test_manifest_grades():
    assert tool_risk("google_docs.create") == "draft"
    assert tool_risk("google_docs.write") == "reversible_write"
    # legacy alias still resolves
    assert tool_risk("docs.write") == "reversible_write"


@pytest.mark.asyncio
async def test_requires_drive(make_ctx):
    ctx = make_ctx("google_docs.create", client=FakeClient(connected=set()))
    with pytest.raises(RuntimeError):
        await tool.run("create", instruction="make a doc", params={"name": "x"}, ctx=ctx)
