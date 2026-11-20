"""Group feedback and failed evals. Propose a change only when an edit repeats."""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict

from core.runtime.runs.models import FeedbackSignal
from core.runtime.runs.store import RunStore
from evals.run import available_agents, run as run_evals

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def preference_key(revision: str) -> str:
    """The same edit, ignoring case, punctuation, and extra whitespace."""
    folded = revision.casefold()
    cleaned = _PUNCTUATION.sub(" ", folded)
    return _SPACE.sub(" ", cleaned).strip()


def propose(store: RunStore | None = None) -> dict:
    """Collect feedback and offline eval failures, then emit repeated-edit candidates."""
    signals = (store or RunStore()).list_feedback()
    failures = asyncio.run(run_evals(available_agents(), live=False))
    return {
        "feedback_groups": _feedback_groups(signals),
        "eval_failures": _eval_failures(failures),
        "candidates": _candidates(signals),
    }


def _feedback_groups(signals: list[FeedbackSignal]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for signal in signals:
        if not signal.organization_id:
            continue
        grouped[(signal.organization_id, signal.agent_id)].append(
            {
                "run_id": signal.run_id,
                "revision": signal.revision,
                "rating": signal.rating,
            }
        )
    return [
        {"organization_id": org, "agent_id": agent, "steps": steps}
        for (org, agent), steps in grouped.items()
    ]


def _eval_failures(results) -> list[dict]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for result in results:
        if result.passed:
            continue
        grouped[result.agent].append(result.case_id)
    return [
        {"agent_id": agent, "cases": cases}
        for agent, cases in sorted(grouped.items())
    ]


def _candidates(signals: list[FeedbackSignal]) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for signal in signals:
        if not signal.organization_id:
            continue
        key = preference_key(signal.revision)
        if not key:
            continue
        grouped[(signal.organization_id, signal.agent_id, key)].append(signal.run_id)
    candidates = []
    for (org, agent, key), run_ids in grouped.items():
        if len(run_ids) < 2:
            continue
        seen: list[str] = []
        for run_id in run_ids:
            if run_id not in seen:
                seen.append(run_id)
        if len(seen) < 2:
            continue
        candidates.append(
            {
                "organization_id": org,
                "agent_id": agent,
                "preference": key,
                "run_ids": seen,
            }
        )
    return candidates
