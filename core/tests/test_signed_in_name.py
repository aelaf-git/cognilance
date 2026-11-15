"""The coordinator sees the signed-in display name from account settings."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from core.context.request import current_user_id
from core.context.users.accounts import AccountStore
from core.context.users.identity import signed_in_display_name
from pipelines.coordinator_board.loop import _think_prompt


def test_signed_in_display_name_reads_account_settings(tmp_path, monkeypatch):
    store = AccountStore(str(tmp_path / "accounts.db"))
    store.init_db()
    account = store.create(
        email="aelaf@example.com",
        password="password1",
        display_name="Aelaf Eskindir",
    )
    monkeypatch.setattr("core.context.users.identity._store", store)

    assert signed_in_display_name(account.id) == "Aelaf Eskindir"
    assert signed_in_display_name("default") == ""
    assert signed_in_display_name("") == ""
    assert signed_in_display_name("missing-user") == ""


def test_think_prompt_includes_signed_in_name(monkeypatch):
    monkeypatch.setattr(
        "pipelines.coordinator_board.loop.signed_in_display_name",
        lambda: "Aelaf Eskindir",
    )
    prompt = _think_prompt({"messages": [HumanMessage(content="What is my name?")]})
    assert "The signed-in user's name is Aelaf Eskindir." in prompt
    assert "account settings" in prompt


def test_think_prompt_omits_name_when_signed_out(monkeypatch):
    token = current_user_id.set("default")
    monkeypatch.setattr("core.context.users.identity._store", None)
    try:
        prompt = _think_prompt({"messages": [HumanMessage(content="Hello")]})
    finally:
        current_user_id.reset(token)
    assert "signed-in user's name" not in prompt
