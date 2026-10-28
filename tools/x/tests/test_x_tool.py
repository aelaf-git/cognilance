import pytest

from core.context.drafts.store import DraftStore
from core.context.request import current_conversation_id
from tools.conftest import FakeClient
from tools.registry import load_manifests, tool_risk
from tools.x import tool


@pytest.fixture
def draft_db(tmp_path, monkeypatch):
    path = tmp_path / "coord.db"
    monkeypatch.setattr(
        "core.context.drafts.store.ensure_db_dir",
        lambda: path,
    )
    DraftStore(str(path)).init_db()
    return path


def test_manifest_grades():
    manifest = load_manifests()["x"]
    assert set(manifest.actions) >= {"draft", "post", "me"}
    assert tool_risk("x.post") == "irreversible"
    assert tool_risk("x.draft") == "draft"


@pytest.mark.asyncio
async def test_post_requires_connection(make_ctx, draft_db):
    current_conversation_id.set("c1")
    DraftStore(str(draft_db)).save_draft("c1", "x_post", {"text": "hello"})
    ctx = make_ctx("x.post", client=FakeClient(connected=set()))
    with pytest.raises(RuntimeError, match="not connected"):
        await tool.run("post", instruction="post it", params={}, ctx=ctx)


@pytest.mark.asyncio
async def test_post_requires_draft(make_ctx, draft_db):
    current_conversation_id.set("c2")
    client = FakeClient(connected={"x"}, responses={"create_post": {"post_id": "1"}})
    ctx = make_ctx("x.post", client=client)
    with pytest.raises(RuntimeError, match="No pending"):
        await tool.run("post", instruction="post it", params={}, ctx=ctx)


@pytest.mark.asyncio
async def test_draft_then_post(make_ctx, draft_db):
    current_conversation_id.set("c3")
    client = FakeClient(
        connected={"x"},
        responses={"create_post": {"post_id": "99", "url": "https://x.com/i/web/status/99"}},
    )
    ctx_draft = make_ctx("x.draft", client=client)
    out = await tool.run(
        "draft", instruction='tweet "Ship social agents"', params={}, ctx=ctx_draft
    )
    assert out.data["status"] == "draft"
    ctx_post = make_ctx("x.post", client=client)
    posted = await tool.run("post", instruction="post it", params={}, ctx=ctx_post)
    assert client.calls[-1][:2] == ("x", "create_post")
    assert posted.data["status"] == "posted"
