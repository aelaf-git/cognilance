import pytest

from tools.calendar import tool
from tools.conftest import FakeClient


@pytest.mark.asyncio
async def test_requires_calendar(make_ctx):
    ctx = make_ctx("calendar.list", client=FakeClient(connected=set()))
    with pytest.raises(RuntimeError):
        await tool.run("list", instruction="what's on today", params={}, ctx=ctx)
