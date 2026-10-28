import pytest

from core.context.drafts.store import DraftStore
from core.context.request import current_conversation_id
from tools.conftest import FakeClient
from tools.reddit import tool
from tools.registry import tool_risk


@pytest.fixture
def draft_db(tmp_path, monkeypatch):
    path = tmp_path / "coord.db"
    monkeypatch.setattr("core.context.drafts.store.ensure_db_dir", lambda: path)
    DraftStore(str(path)).init_db()
    return path


def test_manifest_post_irreversible():
    assert tool_risk("reddit.post") == "irreversible"


@pytest.mark.asyncio
async def test_draft_gate(make_ctx, draft_db):
    current_conversation_id.set("r1")
    client = FakeClient(connected={"reddit"})
    ctx = make_ctx("reddit.post", client=client)
    with pytest.raises(RuntimeError, match="No pending"):
        await tool.run("post", instruction="post it", params={}, ctx=ctx)


@pytest.mark.asyncio
async def test_draft_then_post(make_ctx, draft_db):
    current_conversation_id.set("r2")
    client = FakeClient(
        connected={"reddit"},
        responses={"submit_post": {"post_id": "t3_abc", "url": "https://reddit.com/r/test"}},
    )
    draft_ctx = make_ctx("reddit.draft", client=client)
    await tool.run(
        "draft",
        instruction="post to r/test",
        params={"subreddit": "test", "title": "Hello", "text": "World"},
        ctx=draft_ctx,
    )
    post_ctx = make_ctx("reddit.post", client=client)
    out = await tool.run("post", instruction="post it", params={}, ctx=post_ctx)
    assert client.calls[-1][:2] == ("reddit", "submit_post")
    assert out.data["status"] == "posted"
