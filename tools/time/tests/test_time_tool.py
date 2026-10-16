import pytest

from tools.time import tool


@pytest.mark.asyncio
async def test_now(make_ctx):
    out = await tool.run("now", instruction="", params={}, ctx=make_ctx("time.now"))
    assert "timezone" in out.data or out.data
    assert out.text
