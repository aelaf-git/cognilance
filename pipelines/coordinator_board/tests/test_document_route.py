"""A specific document is a Word file. A vague request asks. A dead integration stops."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from pipelines.coordinator_board.execute import format_brief
from pipelines.coordinator_board.loop import act, evaluate
from pipelines.coordinator_board.models import Brief, Delegation, ThinkDecision
from pipelines.coordinator_board.roster import build_roster

RELATIVITY = (
    "Hey. Can you Generate a Document with two pages about General Theory of Relativity?"
)


def _decision(**kwargs) -> ThinkDecision:
    base = {
        "user_ask": "test",
        "already_known": "",
        "missing": "",
        "next_step": "act",
        "action": "delegate",
    }
    base.update(kwargs)
    return ThinkDecision(**base)


def _report_brief() -> Brief:
    return Brief(
        goal="Draft a comprehensive two-page document about the General Theory of Relativity.",
        constraints=["Must be detailed enough to span approximately two pages.", "Must be drafted in Google Docs."],
        success_criteria=["Document is created in Google Docs."],
    )


def _state(message: str, decision: ThinkDecision, *, observations: list | None = None, prior: str = "") -> dict:
    messages = []
    if prior:
        messages.append(AIMessage(content=prior))
    messages.append(HumanMessage(content=message))
    return {
        "messages": messages,
        "last_decision": decision.model_dump(),
        "roster": build_roster().model_dump(),
        "observations": list(observations or []),
        "delegation_count": 0,
        "revision": {},
        "iteration": 1,
        "verdicts": [],
        "retries": {},
        "accepted_ids": [],
        "loop_status": "continue",
        "halt": False,
    }


@pytest.mark.asyncio
async def test_vague_requests_ask_and_do_not_delegate():
    execute = AsyncMock()
    decision = _decision(
        delegations=[
            Delegation(
                agent_id="report_writer",
                brief=Brief(goal="Write a document for the user.", success_criteria=["A document exists."]),
            )
        ]
    )
    with patch("pipelines.coordinator_board.loop.execute_brief", execute):
        document = await act(_state("Write a document", decision))
        send = await act(_state("send it", decision))
    execute.assert_not_called()
    assert document["last_decision"]["action"] == "ask_user"
    assert document["pending_observations"][0]["payload"]["text"] == "What should the document be about?"
    assert send["last_decision"]["action"] == "ask_user"
    assert send["pending_observations"][0]["payload"]["text"] == "Who should I send it to?"


@pytest.mark.asyncio
async def test_follow_up_on_an_open_document_still_runs():
    execute = AsyncMock(return_value={"text": "Updated the file.", "data": {"document_id": "doc_abcabcabcabc"}, "tool": "docx.write"})
    decision = _decision(
        delegations=[
            Delegation(
                agent_id="docx_agent",
                brief=Brief(goal="Add a heading to the open biography.", success_criteria=["The heading is in the file."]),
            )
        ]
    )
    state = _state(
        "Add a heading",
        decision,
        prior="The open file is a biography of Stephen Hawking.",
    )
    with patch("pipelines.coordinator_board.loop.execute_brief", execute):
        await act(state)
    execute.assert_awaited()
    assert execute.await_args.args[0] == "docx_agent"


@pytest.mark.asyncio
async def test_relativity_document_is_written_as_a_word_file():
    execute = AsyncMock(return_value={"text": "Created the Word file.", "data": {"document_id": "doc_abcabcabcabc"}, "tool": "docx.create"})
    decision = _decision(
        user_ask="Draft a comprehensive two-page document about the General Theory of Relativity.",
        delegations=[Delegation(agent_id="report_writer", brief=_report_brief())],
    )
    with patch("pipelines.coordinator_board.loop.execute_brief", execute):
        await act(_state(RELATIVITY, decision))
    execute.assert_awaited_once()
    assert execute.await_args.args[0] == "docx_agent"
    brief = format_brief(execute.await_args.args[1]).lower()
    assert "google" not in brief
    assert "relativity" in brief
    assert "word file" in brief


@pytest.mark.asyncio
async def test_explicit_google_doc_stays_with_report_writer():
    execute = AsyncMock(return_value={"text": "Drafted the Google Doc.", "data": {}, "tool": "google_docs.create"})
    decision = _decision(
        delegations=[Delegation(agent_id="report_writer", brief=_report_brief())],
    )
    with patch("pipelines.coordinator_board.loop.execute_brief", execute):
        await act(_state("Create a Google Doc about relativity", decision))
    assert execute.await_args.args[0] == "report_writer"


@pytest.mark.asyncio
async def test_disconnected_drive_does_not_revise_the_same_agent():
    decision = _decision(
        delegations=[Delegation(agent_id="report_writer", brief=_report_brief())],
    )
    state = _state(
        "Create a Google Doc about relativity",
        decision,
        observations=[
            {
                "id": "obs_drive",
                "source": "report_writer",
                "status": "error",
                "payload": {"error": "Google Drive is not connected", "text": ""},
            }
        ],
    )
    state["last_decision"] = decision.model_dump()
    update = await evaluate(state)
    assert update["revision"] == {}
    verdict = update["verdicts"][-1]
    assert verdict["verdict"] == "reroute"
    assert verdict["reason"] == "Google Drive is not connected"
    assert "Re-brief" not in (verdict.get("feedback") or "")

    execute = AsyncMock()
    with patch("pipelines.coordinator_board.loop.execute_brief", execute):
        acted = await act(state)
    execute.assert_not_called()
    assert acted["pending_observations"][0]["payload"]["text"] == "Google Drive is not connected"


@pytest.mark.asyncio
async def test_local_document_switches_to_word_after_drive_is_down():
    execute = AsyncMock(return_value={"text": "Created the Word file.", "data": {"document_id": "doc_abcabcabcabc"}, "tool": "docx.create"})
    decision = _decision(
        delegations=[Delegation(agent_id="report_writer", brief=_report_brief())],
    )
    state = _state(
        RELATIVITY,
        decision,
        observations=[
            {
                "id": "obs_drive",
                "source": "report_writer",
                "status": "error",
                "payload": {"error": "Google Drive is not connected", "text": ""},
            }
        ],
    )
    with patch("pipelines.coordinator_board.loop.execute_brief", execute):
        await act(state)
    execute.assert_awaited_once()
    assert execute.await_args.args[0] == "docx_agent"
