"""engineering_agent reads one selected repository and reports HTTP errors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents.loader import get_role, load_roles
from core.broker.store import IntegrationStore
from core.context.projects.store import ProjectStore
from core.context.request import current_mission_id
from core.runtime.board.store import BoardStore
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.schema import SpecialistAction, VerificationResult
from pipelines.coordinator_board.specialists import _run_specialist
from tools.registry import load_manifests, validate_tool_ids

_PULL_URL = "https://github.com/acme/app/pull/7"
_COMMIT_URL = "https://github.com/acme/app/commit/abc123"
_PULL_TIME = "2026-11-01T12:00:00Z"
_INVENTED = "invented/repo"
_GITHUB_READS = (
    "github.list_commits",
    "github.list_pull_requests",
    "github.list_issues",
    "github.get_repo",
)


class _Script:
    def __init__(self, actions: list[SpecialistAction]) -> None:
        self._actions = list(actions)

    async def ainvoke(self, _prompt: str) -> SpecialistAction:
        if not self._actions:
            raise RuntimeError("no more actions")
        return self._actions.pop(0)


class _GitHub:
    def __init__(self, *, connected: bool, payload: Any = None) -> None:
        self.connected = connected
        self.payload = payload
        self.calls: list[tuple[str, dict]] = []

    def is_connected(self, _user_id: str, _integration_id: str) -> bool:
        return self.connected

    async def run(self, _user_id: str, _integration_id: str, action: str, params: dict) -> Any:
        self.calls.append((action, dict(params)))
        if isinstance(self.payload, dict) and action in self.payload:
            return self.payload[action]
        return self.payload


@pytest.fixture
def world(tmp_path, monkeypatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)
    projects = ProjectStore(db)
    runs = RunStore(db)
    board = BoardStore(db)
    for store in (projects, runs, board):
        store.init_db()
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    ours = projects.create_project("org-a", "Launch", created_by="ada")
    theirs = projects.create_project("org-b", "Secret program", created_by="bea")
    projects.create_task(
        ours.id,
        organization_id="org-a",
        title="Ship the login fix",
        created_by="ada",
        deadline=past,
        status="open",
    )
    projects.create_task(
        theirs.id,
        organization_id="org-b",
        title="Other org secret",
        created_by="bea",
        deadline=past,
        status="open",
    )
    run = runs.create_run(
        instruction="Report open pull requests",
        thread_id="thread-a",
        organization_id="org-a",
        user_id="ada",
        run_id="run-a",
    )
    return {"board": board, "run": run, "runs": runs, "db": db}


def _select_repo(world) -> None:
    grants = IntegrationStore(world["db"])
    grants.init_db()
    grants.save_org_grant(
        organization_id="org-a",
        integration="github",
        access_token="ghp_test_secret",
        refresh_token=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    grants.set_selected_repos("org-a", "github", ["101"])


async def _specialist(world, actions: list[SpecialistAction], client: _GitHub) -> dict:
    world["board"].create_task(
        run_id=world["run"].id,
        title="GitHub",
        instruction="Report pull requests",
        assignee_role="engineering_agent",
    )
    token = current_mission_id.set(world["run"].id)
    try:
        with (
            patch("core.broker.client.IntegrationClient", return_value=client),
            patch(
                "pipelines.coordinator_board.specialists.get_structured_llm",
                return_value=_Script(actions),
            ),
            patch(
                "pipelines.coordinator_board.specialists.verify_task_output",
                new=AsyncMock(return_value=VerificationResult(passed=True, reasoning="ok")),
            ),
        ):
            return await _run_specialist(
                {"run_id": world["run"].id, "messages": []},
                "engineering_agent",
            )
    finally:
        current_mission_id.reset(token)


def _selected_payload() -> dict[str, Any]:
    return {
        "get_repo": {
            "id": 101,
            "full_name": "acme/app",
            "name": "app",
            "owner": {"login": "acme"},
            "html_url": "https://github.com/acme/app",
            "updated_at": _PULL_TIME,
        },
        "list_commits": [
            {
                "sha": "abc123",
                "html_url": _COMMIT_URL,
                "commit": {
                    "message": "Ship the login fix\n\nDetails",
                    "committer": {"date": _PULL_TIME},
                },
            }
        ],
        "list_pull_requests": [
            {
                "id": 7,
                "number": 7,
                "title": "Ship the login fix",
                "html_url": _PULL_URL,
                "updated_at": _PULL_TIME,
            }
        ],
    }


@pytest.mark.asyncio
async def test_selected_repo_lists_commits_and_pull_requests(world):
    _select_repo(world)
    client = _GitHub(connected=True, payload=_selected_payload())
    update = await _specialist(
        world,
        [
            SpecialistAction(status="call_tool", tool="github.list_commits", tool_instruction="{}"),
            SpecialistAction(
                status="call_tool",
                tool="github.list_pull_requests",
                tool_instruction="{}",
            ),
            SpecialistAction(
                status="call_tool",
                tool="projects.search_tasks",
                tool_instruction='{"query": "Ship the login fix"}',
            ),
            SpecialistAction(status="done", answer=""),
        ],
        client,
    )
    result = update["subtask_results"][0]
    items = result["data"]["items"]
    assert items
    assert all(item.get("url") and item.get("updated_at") for item in items)
    rendered = f"{result['text']}\n{result['data']}"
    assert _COMMIT_URL in rendered
    assert _PULL_URL in rendered
    assert _PULL_TIME in rendered
    assert "Ship the login fix" in rendered
    assert "Other org secret" not in rendered
    assert ("get_repo", {"repo_id": "101"}) in client.calls
    assert ("list_commits", {"owner": "acme", "repo": "app"}) in client.calls
    assert ("list_pull_requests", {"owner": "acme", "repo": "app"}) in client.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_http_failure_is_a_tool_error_on_the_run_step(world, status_code):
    client = _GitHub(connected=True, payload={"http_status": status_code})
    update = await _specialist(
        world,
        [
            SpecialistAction(
                status="call_tool",
                tool="github.list_commits",
                tool_instruction='{"owner": "acme", "repo": "app"}',
            ),
            SpecialistAction(status="done", answer=""),
        ],
        client,
    )
    text = update["subtask_results"][0]["text"]
    assert text == f"GitHub API error {status_code}"
    assert text != "No commits."
    steps = world["runs"].list_steps(world["run"].id)
    recorded = [step for step in steps if step.kind == "tool_call"]
    assert recorded
    assert recorded[-1].data["status"] == "error"
    assert recorded[-1].data["status_code"] == status_code


@pytest.mark.asyncio
async def test_missing_connection_says_github_is_not_connected(world):
    client = _GitHub(connected=False, payload=[{"title": "Should not load"}])
    update = await _specialist(
        world,
        [
            SpecialistAction(
                status="call_tool",
                tool="github.list_pull_requests",
                tool_instruction='{"owner": "acme", "repo": "app"}',
            ),
            SpecialistAction(status="done", answer=""),
        ],
        client,
    )
    assert "GitHub is not connected" in update["subtask_results"][0]["text"]
    assert client.calls == []


@pytest.mark.asyncio
async def test_empty_github_list_does_not_invent_a_repository(world):
    client = _GitHub(connected=True, payload=[])
    update = await _specialist(
        world,
        [
            SpecialistAction(
                status="call_tool",
                tool="github.list_commits",
                tool_instruction='{"owner": "acme", "repo": "app"}',
            ),
            SpecialistAction(status="done", answer=""),
        ],
        client,
    )
    text = update["subtask_results"][0]["text"]
    assert text == "No commits."
    assert _INVENTED not in text
    assert update["subtask_results"][0]["data"]["items"] == []


def test_github_read_tool_ids_belong_only_to_engineering_agent():
    load_roles.cache_clear()
    load_manifests.cache_clear()
    assert get_role("engineering_agent") is not None
    assert validate_tool_ids(list(_GITHUB_READS)) == []
    for role_id, pack in load_roles().items():
        listed = [tool for tool in pack.tools if tool in _GITHUB_READS]
        if role_id == "engineering_agent":
            assert listed == list(_GITHUB_READS)
        else:
            assert listed == []
