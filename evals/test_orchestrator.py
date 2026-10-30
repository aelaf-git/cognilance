"""Scripted orchestrator evals. No network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from evals.orchestrator_runner import check_case, run_case, summarize

_CASES = Path(__file__).with_name("orchestrator") / "cases.yaml"
_ROWS: list[dict] = []


def _load() -> list[dict]:
    return list(yaml.safe_load(_CASES.read_text()) or [])


@pytest.fixture(scope="session", autouse=True)
def _orchestrator_report():
    _ROWS.clear()
    yield
    summary = summarize(_ROWS)
    assert summary["cases"] >= 20, summary
    assert summary["hallucination_rate"] == 0, summary
    print("ORCHESTRATOR_EVAL " + json.dumps(summary))


@pytest.mark.parametrize("case", _load(), ids=lambda case: case["id"])
@pytest.mark.asyncio
async def test_orchestrator_case(case: dict):
    outcome = await run_case(case)
    _ROWS.append(outcome)
    check_case(case, outcome)
