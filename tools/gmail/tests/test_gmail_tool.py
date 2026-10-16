import pytest

from tools.conftest import FakeClient
from tools.gmail import tool
from tools.registry import load_manifests, tool_risk


def test_manifest_grades():
    manifest = load_manifests()["gmail"]
    assert set(manifest.actions) >= {"draft", "send", "search"}
    assert tool_risk("gmail.send") == "irreversible"
    assert tool_risk("gmail.draft") == "draft"


@pytest.mark.asyncio
async def test_send_requires_connection(make_ctx):
    ctx = make_ctx("gmail.send", client=FakeClient(connected=set()))
    with pytest.raises(RuntimeError):
        await tool.run("send", instruction="send it", params={"to": "a@b.c"}, ctx=ctx)


@pytest.mark.asyncio
async def test_list_uses_broker(make_ctx):
    client = FakeClient(connected={"gmail"}, responses={"list_emails": {"emails": []}})
    ctx = make_ctx("gmail.list", client=client)
    out = await tool.run("list", instruction="", params={}, ctx=ctx)
    assert client.calls[0][:2] == ("gmail", "list_emails")
    assert out.data == {"emails": []}
