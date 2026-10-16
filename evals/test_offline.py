"""Offline eval cases run as a pytest suite (no network, no credentials)."""

from __future__ import annotations

import pytest

from evals.run import _check_offline, available_agents, load_cases

CASES = [(a, c) for a in available_agents() for c in load_cases(a)]


@pytest.mark.parametrize("agent,case", CASES, ids=[f"{a}/{c['id']}" for a, c in CASES])
def test_offline_case(agent: str, case: dict) -> None:
    result = _check_offline(agent, case)
    assert result.passed, result.detail
