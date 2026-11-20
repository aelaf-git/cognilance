"""A repeated edit in one organization becomes one candidate."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.runtime.runs.store import RunStore
from core.signals import record_feedback
from evals.run import load_cases
from improvement.propose import propose


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", path)
    RunStore(path).init_db()
    return path


def _run(path: str, run_id: str, organization_id: str) -> None:
    RunStore(path).create_run(
        instruction="Write the note",
        thread_id=run_id,
        organization_id=organization_id,
        run_id=run_id,
    )


def _edit(path: str, run_id: str, organization_id: str, revision: str) -> None:
    _run(path, run_id, organization_id)
    record_feedback(
        run_id,
        rating=-1,
        note="Please change this.",
        revision=revision,
        agent_id="project_agent",
    )


def test_two_similar_edits_produce_one_candidate_and_one_edit_does_not(db):
    _edit(db, "run-a", "org-a", "The date is missing.")
    _edit(db, "run-b", "org-a", "the date is missing")
    _edit(db, "run-c", "org-a", "Ship it on Friday.")
    report = propose(RunStore(db))
    matched = [
        item
        for item in report["candidates"]
        if item["preference"] == "the date is missing" and item["organization_id"] == "org-a"
    ]
    assert matched == [
        {
            "organization_id": "org-a",
            "agent_id": "project_agent",
            "preference": "the date is missing",
            "run_ids": ["run-a", "run-b"],
        }
    ]
    assert all(item["preference"] != "ship it on friday" for item in report["candidates"])
    group = next(
        item
        for item in report["feedback_groups"]
        if item["organization_id"] == "org-a" and item["agent_id"] == "project_agent"
    )
    assert [step["run_id"] for step in group["steps"]] == ["run-a", "run-b", "run-c"]


def test_another_organizations_feedback_stays_on_its_own_candidate(db):
    _edit(db, "run-a", "org-a", "The date is missing.")
    _edit(db, "run-b", "org-a", "The date is missing.")
    _edit(db, "run-c", "org-b", "The date is missing.")
    _edit(db, "run-d", "org-b", "The date is missing!")
    report = propose(RunStore(db))
    by_org = {item["organization_id"]: item for item in report["candidates"]}
    assert by_org["org-a"]["run_ids"] == ["run-a", "run-b"]
    assert by_org["org-b"]["run_ids"] == ["run-c", "run-d"]
    assert "run-a" not in by_org["org-b"]["run_ids"]
    assert "run-c" not in by_org["org-a"]["run_ids"]


def test_a_failed_eval_is_grouped_by_agent_and_not_attached_to_feedback(db, monkeypatch):
    _edit(db, "run-a", "org-a", "The date is missing.")
    _edit(db, "run-b", "org-a", "The date is missing.")

    def with_failure(agent: str):
        cases = load_cases(agent)
        if agent == "researcher":
            cases = [
                *cases,
                {
                    "id": "forced_miss",
                    "instruction": "Say hello.",
                    "expect": {"tool": "not.a.real.tool"},
                },
            ]
        return cases

    monkeypatch.setattr("evals.run.load_cases", with_failure)
    report = propose(RunStore(db))
    researcher = next(item for item in report["eval_failures"] if item["agent_id"] == "researcher")
    assert "forced_miss" in researcher["cases"]
    assert all("forced_miss" not in item["run_ids"] for item in report["candidates"])
    for group in report["feedback_groups"]:
        assert all("forced_miss" not in step["run_id"] for step in group["steps"])
        if group["organization_id"] != "org-a":
            assert group["steps"] == []
