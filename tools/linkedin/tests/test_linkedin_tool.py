import pytest

from core.context.drafts.store import DraftStore
from core.context.request import current_conversation_id
from tools.conftest import FakeClient
from tools.linkedin import tool
from tools.registry import tool_risk


@pytest.fixture
def draft_db(tmp_path, monkeypatch):
    path = tmp_path / "coord.db"
    monkeypatch.setattr("core.context.drafts.store.ensure_db_dir", lambda: path)
    DraftStore(str(path)).init_db()
    return path


def test_manifest_post_irreversible():
    assert tool_risk("linkedin.post") == "irreversible"


@pytest.mark.asyncio
async def test_draft_gate(make_ctx, draft_db):
    current_conversation_id.set("l1")
    client = FakeClient(connected={"linkedin"})
    ctx = make_ctx("linkedin.post", client=client)
    with pytest.raises(RuntimeError, match="No pending"):
        await tool.run("post", instruction="post it", params={}, ctx=ctx)


@pytest.mark.asyncio
async def test_draft_then_post(make_ctx, draft_db):
    current_conversation_id.set("l2")
    client = FakeClient(
        connected={"linkedin"},
        responses={"create_post": {"post_id": "urn:li:share:1"}},
    )
    draft_ctx = make_ctx("linkedin.draft", client=client)
    await tool.run(
        "draft",
        instruction='post "Shipping LinkedIn agent"',
        params={},
        ctx=draft_ctx,
    )
    post_ctx = make_ctx("linkedin.post", client=client)
    out = await tool.run("post", instruction="publish it", params={}, ctx=post_ctx)
    assert client.calls[-1][:2] == ("linkedin", "create_post")
    assert out.data["status"] == "posted"
