"""Roster construction and code-level action checks."""

from __future__ import annotations

from pipelines.coordinator_board.models import Brief, Delegation, Roster, RosterEntry, ThinkDecision
from pipelines.coordinator_board.roster import build_roster
from pipelines.coordinator_board.validate import (
    apply_trivial_guard,
    classify_payload,
    split_delegations,
    trivial_reply,
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


def _brief(**kwargs) -> Brief:
    base = {
        "goal": "Find recent public notes on checkpoints",
        "context": "User asked for public notes.",
        "success_criteria": ["At least one sourced note"],
        "budget": "one pass",
    }
    base.update(kwargs)
    return Brief(**base)


def test_roster_is_live_manifests_with_gaps():
    roster = build_roster()
    ids = {agent.id for agent in roster.agents}
    assert "researcher" in ids
    assert "email_agent" in ids
    assert "coordinator" not in ids
    assert all(agent.status == "available" for agent in roster.agents)
    researcher = next(agent for agent in roster.agents if agent.id == "researcher")
    assert "web.search" in researcher.required_inputs
    assert researcher.output_shape
    assert "Slide decks" in roster.not_available
    assert "CRM records" in roster.not_available
    assert "Calendar events and invites" in roster.not_available
    assert "Public web research" not in roster.not_available
    assert "Email drafts and sending" not in roster.not_available


def test_unknown_agent_is_rejected_before_execution():
    roster = build_roster()
    decision = _decision(
        delegations=[Delegation(agent_id="slides_bot", brief=_brief())],
    )
    accepted, errors = split_delegations(decision, roster)
    assert accepted == []
    assert errors[0]["payload"]["error"] == "no such agent"
    assert errors[0]["status"] == "error"


def test_offline_agent_is_rejected():
    roster = build_roster()
    agents = []
    for agent in roster.agents:
        if agent.id == "researcher":
            agents.append(agent.model_copy(update={"status": "offline"}))
        else:
            agents.append(agent)
    roster = Roster(agents=agents, not_available=roster.not_available)
    decision = _decision(
        delegations=[Delegation(agent_id="researcher", brief=_brief())],
    )
    accepted, errors = split_delegations(decision, roster)
    assert accepted == []
    assert errors[0]["payload"]["error"] == "agent offline"


def test_vague_brief_is_rejected():
    roster = build_roster()
    decision = _decision(
        delegations=[
            Delegation(
                agent_id="researcher",
                brief=_brief(goal="Research", success_criteria=[]),
            )
        ],
    )
    accepted, errors = split_delegations(decision, roster)
    assert accepted == []
    assert errors[0]["payload"]["error"] == "vague brief"


def test_legacy_role_id_resolves_to_a_real_agent():
    roster = build_roster()
    decision = _decision(
        delegations=[Delegation(agent_id="reporter", brief=_brief())],
    )
    accepted, errors = split_delegations(decision, roster)
    assert errors == []
    assert accepted[0].agent_id == "report_writer"


def test_greeting_cannot_delegate():
    assert trivial_reply("hey!") == "Hey. What can I help with?"
    decision = apply_trivial_guard(
        "hey!",
        _decision(delegations=[Delegation(agent_id="researcher", brief=_brief())]),
    )
    assert decision.action == "answer_directly"
    assert decision.delegations == []


def test_classify_empty_error_and_malformed():
    assert classify_payload("researcher", {"text": "", "data": {}}) == "empty"
    assert classify_payload("researcher", {"text": "nope", "data": {"error": "timeout"}}) == "error"
    assert (
        classify_payload("email_agent", {"text": "bad", "data": {"result": {"bogus": 1}}})
        == "partial"
    )
    assert classify_payload("researcher", {"text": "A sourced note.", "data": {}}) == "ok"


def test_roster_entry_round_trip():
    entry = RosterEntry(id="researcher", description="web", status="available")
    assert entry.model_validate(entry.model_dump()).id == "researcher"
