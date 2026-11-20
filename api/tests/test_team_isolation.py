"""One organization cannot read another's conversation, run, project, or alert."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from api.auth.guard import is_public_request
from api.auth.session import get_user_id
from api.routes import alerts, auth, conversations, organizations, projects, runs
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import OrgStore
from core.context.projects.store import ProjectStore
from core.context.request import current_mission_id, current_user_id, current_user_timezone
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.accounts import AccountStore
from core.context.users.store import UserPreferencesStore
from core.context.users.timezone import activate_user_timezone, client_timezone_from_request
from core.runtime.board.store import BoardStore
from core.runtime.missions.models import MissionStatus
from core.runtime.missions.store import MissionStore
from core.runtime.runs.models import RunStatus
from core.runtime.runs.store import RunStore
from pipelines.coordinator_board.coordinator import coordinator_assemble, coordinator_plan
from pipelines.coordinator_board.schema import SpecialistAction, VerificationResult
from pipelines.coordinator_board.specialists import specialists_fanout
from pipelines.weekly_report.graph import preset
from tools.github import tool as github_tool
from tools.registry import ToolContext
from workers.schedulers.detection import detect_alerts


class _EmptyDrafts:
    def get_active_doc(self, conversation_id: str):
        return None


class _Script:
    def __init__(self, actions: list[SpecialistAction]) -> None:
        self._actions = list(actions)

    async def ainvoke(self, _prompt: str) -> SpecialistAction:
        if not self._actions:
            raise RuntimeError("no more actions")
        return self._actions.pop(0)


class _Graph:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.sent: list[dict] = []

    async def aget_state(self, config):
        return SimpleNamespace(next=(), interrupts=(), values={})

    async def astream(self, graph_input, config, stream_mode=None):
        self.calls.append({"input": graph_input, "config": config})
        if isinstance(graph_input, Command) and graph_input.resume == {"approved": True}:
            self.sent.append(dict(graph_input.resume))
        yield "values", {"messages": []}


class _NoNetwork:
    def __init__(self, *args, **kwargs):
        raise AssertionError("external HTTP is stubbed")

    async def __aenter__(self):
        raise AssertionError("external HTTP is stubbed")

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    monkeypatch.setenv("COORDINATOR_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", db)

    accounts = AccountStore(db)
    orgs = OrgStore(db)
    prefs = UserPreferencesStore(db)
    conv_store = ConversationStore(db)
    run_store = RunStore(db)
    board = BoardStore(db)
    missions = MissionStore(db)
    subs = SubscriptionStore(db)
    project_store = ProjectStore(db)
    for store in (accounts, orgs, prefs, conv_store, run_store, board, missions, subs, project_store):
        store.init_db()

    monkeypatch.setattr(auth, "account_store", accounts)
    monkeypatch.setattr("api.deps.account_store", accounts)
    monkeypatch.setattr("api.deps.org_store", orgs)
    monkeypatch.setattr("api.deps.project_store", project_store)
    monkeypatch.setattr("core.context.users.timezone._store", prefs)
    monkeypatch.setattr(conversations, "conv_store", conv_store)
    monkeypatch.setattr(conversations, "mission_store", missions)
    monkeypatch.setattr(conversations, "sub_store", subs)
    monkeypatch.setattr(conversations, "DraftStore", _EmptyDrafts)
    monkeypatch.setattr(conversations, "active_document_id", lambda _conversation_id: None)
    monkeypatch.setattr(runs, "run_store", run_store)
    monkeypatch.setattr(runs, "mission_store", missions)
    monkeypatch.setattr(runs, "board_store", board)
    monkeypatch.setattr(runs, "conv_store", conv_store)

    graph = _Graph()

    async def ensure_graph(*, with_checkpointer: bool = True):
        return graph

    monkeypatch.setattr("core.runtime.runner.ensure_graph", ensure_graph)

    app = FastAPI()

    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        user_id = get_user_id(request)
        request.state.user_id = user_id
        if not user_id and not is_public_request(request):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        user_token = None
        tz_token = None
        if user_id:
            user_token = current_user_id.set(user_id)
            tz_token = activate_user_timezone(
                user_id, from_client=client_timezone_from_request(request)
            )
        try:
            return await call_next(request)
        finally:
            if tz_token is not None:
                current_user_timezone.reset(tz_token)
            if user_token is not None:
                current_user_id.reset(user_token)

    for router in (
        auth.router,
        organizations.router,
        conversations.router,
        projects.router,
        runs.router,
        alerts.router,
    ):
        app.include_router(router)

    with TestClient(app) as client:
        yield {
            "client": client,
            "db": db,
            "orgs": orgs,
            "conversations": conv_store,
            "runs": run_store,
            "board": board,
            "missions": missions,
            "projects": project_store,
            "graph": graph,
        }


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "password1", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _login(client: TestClient, email: str) -> None:
    client.cookies.clear()
    response = client.post("/auth/login", json={"email": email, "password": "password1"})
    assert response.status_code == 200, response.text


def _membership_count(db: str, organization_id: str, account_id: str) -> int:
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM memberships
            WHERE organization_id = ? AND account_id = ?
            """,
            (organization_id, account_id),
        ).fetchone()
    return int(row[0])


def _waiting_run(world, *, user_id: str, organization_id: str, thread_id: str):
    mission = world["missions"].create_mission(
        instruction="Send the note",
        thread_id=thread_id,
        user_id=user_id,
        organization_id=organization_id,
    )
    world["missions"].update_status(mission.id, MissionStatus.RUNNING)
    run = world["runs"].create_run(
        instruction="Send the note",
        thread_id=thread_id,
        user_id=user_id,
        organization_id=organization_id,
        mission_id=mission.id,
        run_id=mission.id,
    )
    world["runs"].update_status(
        run.id,
        RunStatus.WAITING_APPROVAL,
        pending_approval={"tool": "gmail.send", "approved": False},
    )
    return run


def test_register_returns_one_owner_organization(world):
    client = world["client"]
    ada = _register(client, "ada@example.com")
    listed = client.get("/organizations")
    assert listed.status_code == 200, listed.text
    organizations = listed.json()["organizations"]
    assert len(organizations) == 1
    assert organizations[0]["role"] == "owner"
    assert organizations[0]["id"] == world["orgs"].active_for_account(ada["id"])


def test_invitation_is_accepted_once_and_another_organization_is_not_found(world):
    client = world["client"]
    ada = _register(client, "ada@example.com")
    org_id = world["orgs"].active_for_account(ada["id"])
    assert org_id
    _register(client, "cam@example.com")
    _register(client, "bea@example.com")
    _login(client, "ada@example.com")

    created = client.post(
        f"/organizations/{org_id}/invitations",
        json={"email": "cam@example.com"},
    )
    assert created.status_code == 200, created.text
    token = created.json()["token"]

    _login(client, "cam@example.com")
    cam_profile = client.get("/auth/me")
    assert cam_profile.status_code == 200, cam_profile.text
    cam_account = cam_profile.json()["id"]
    accepted = client.post(f"/invitations/{token}/accept")
    assert accepted.status_code == 200, accepted.text
    again = client.post(f"/invitations/{token}/accept")
    assert again.status_code == 200, again.text
    assert _membership_count(world["db"], org_id, cam_account) == 1

    _login(client, "ada@example.com")
    conversation = client.post("/conversations")
    assert conversation.status_code == 200, conversation.text
    conversation_id = conversation.json()["id"]
    project = client.post("/projects", json={"title": "Launch"})
    assert project.status_code == 200, project.text
    project_id = project.json()["id"]
    run = world["runs"].create_run(
        instruction="Keep going",
        thread_id="thread-ada",
        user_id=ada["id"],
        organization_id=org_id,
    )
    alert = world["orgs"].add_alert(org_id, "Ada's alert")

    _login(client, "bea@example.com")
    assert client.get(f"/conversations/{conversation_id}").status_code == 404
    assert client.get(f"/runs/{run.id}").status_code == 404
    assert client.get(f"/projects/{project_id}").status_code == 404
    assert client.post(f"/alerts/{alert.id}/acknowledge").status_code == 404


def test_two_members_read_the_same_conversation(world):
    client = world["client"]
    ada = _register(client, "ada@example.com")
    org_id = world["orgs"].active_for_account(ada["id"])
    assert org_id
    _register(client, "cam@example.com")
    _login(client, "ada@example.com")
    invited = client.post(
        f"/organizations/{org_id}/invitations",
        json={"email": "cam@example.com"},
    )
    assert invited.status_code == 200, invited.text
    _login(client, "cam@example.com")
    accepted = client.post(f"/invitations/{invited.json()['token']}/accept")
    assert accepted.status_code == 200, accepted.text

    _login(client, "ada@example.com")
    created = client.post("/conversations")
    assert created.status_code == 200, created.text
    conversation_id = created.json()["id"]
    world["conversations"].append_message(
        conversation_id, role="user", content="Hello from Ada", author_id=ada["id"]
    )
    world["conversations"].append_message(
        conversation_id, role="assistant", content="Hello Ada"
    )

    ada_view = client.get(f"/conversations/{conversation_id}")
    _login(client, "cam@example.com")
    cam_view = client.get(f"/conversations/{conversation_id}")
    assert ada_view.status_code == 200
    assert cam_view.status_code == 200
    assert [item["content"] for item in ada_view.json()["messages"]] == [
        "Hello from Ada",
        "Hello Ada",
    ]
    assert [item["id"] for item in ada_view.json()["messages"]] == [
        item["id"] for item in cam_view.json()["messages"]
    ]


@pytest.mark.asyncio
async def test_two_specialists_keep_the_other_organizations_task_out(world):
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    ours = world["projects"].create_project("org-a", "Launch", created_by="ada")
    theirs = world["projects"].create_project("org-b", "Secret program", created_by="bea")
    world["projects"].create_task(
        ours.id,
        organization_id="org-a",
        title="File the brief",
        created_by="ada",
        deadline=past,
        status="open",
    )
    world["projects"].create_task(
        theirs.id,
        organization_id="org-b",
        title="Other org secret",
        created_by="bea",
        deadline=past,
        status="open",
    )
    run = world["runs"].create_run(
        instruction="Work the board",
        thread_id="thread-board",
        organization_id="org-a",
        user_id="ada",
    )
    collect = world["board"].create_task(
        run_id=run.id,
        title="Collect work tasks",
        instruction="List this organization's work tasks.",
        assignee_role="project_agent",
    )
    world["board"].create_task(
        run_id=run.id,
        title="Draft the note",
        instruction="Write the note from the collected tasks.",
        assignee_role="report_writer",
        depends_on=[collect.id],
    )
    script = _Script(
        [
            SpecialistAction(status="call_tool", tool="projects.search_tasks", tool_instruction="{}"),
            SpecialistAction(status="done", answer=""),
            SpecialistAction(status="done", answer="The note stays with this organization."),
        ]
    )
    token = current_mission_id.set(run.id)
    try:
        with (
            patch(
                "pipelines.coordinator_board.specialists.get_structured_llm",
                return_value=script,
            ),
            patch(
                "pipelines.coordinator_board.specialists.verify_task_output",
                new=AsyncMock(return_value=VerificationResult(passed=True, reasoning="ok")),
            ),
        ):
            update = await specialists_fanout(
                {
                    "run_id": run.id,
                    "messages": [HumanMessage(content="Work the board")],
                }
            )
    finally:
        current_mission_id.reset(token)

    results = update["subtask_results"]
    assert {item["assignee"] for item in results} >= {"project_agent", "report_writer"}
    rendered = "\n".join(str(item.get("text") or "") for item in results)
    assert "File the brief" in rendered
    assert "Other org secret" not in rendered
    assert "The note stays with this organization." in rendered


@pytest.mark.asyncio
async def test_github_403_is_a_tool_error_and_does_not_call_the_network():
    class _Client:
        def __init__(self) -> None:
            self.calls: list[tuple] = []

        def is_connected(self, user_id: str, integration_id: str) -> bool:
            return True

        async def run(self, user_id: str, integration: str, action: str, params: dict):
            self.calls.append((integration, action, params))
            return {"http_status": 403}

    client = _Client()
    with patch("httpx.AsyncClient", _NoNetwork):
        output = await github_tool.run(
            "list_commits",
            instruction="",
            params={"owner": "acme", "repo": "app"},
            ctx=ToolContext(
                role_id="engineering_agent",
                user_id="ada",
                client=client,
                tool_id="github.list_commits",
                risk="read",
            ),
        )
    assert output.status == "error"
    assert output.text == "GitHub API error 403"
    assert client.calls == [("github", "list_commits", {"owner": "acme", "repo": "app"})]


def test_recovery_requeues_a_running_run_and_leaves_approval(world):
    ada = _register(world["client"], "ada@example.com")
    org_id = world["orgs"].active_for_account(ada["id"])
    assert org_id
    running = world["missions"].create_mission(
        instruction="Keep going",
        thread_id="thread-running",
        user_id=ada["id"],
        organization_id=org_id,
    )
    world["missions"].update_status(running.id, MissionStatus.RUNNING)
    world["runs"].create_run(
        instruction="Keep going",
        thread_id="thread-running",
        user_id=ada["id"],
        organization_id=org_id,
        mission_id=running.id,
        run_id=running.id,
    )
    world["runs"].update_status(running.id, RunStatus.RUNNING)
    waiting = _waiting_run(world, user_id=ada["id"], organization_id=org_id, thread_id="thread-waiting")

    from core.runtime.runner import recover_interrupted_runs

    recover_interrupted_runs()
    assert world["runs"].get_run(running.id).status == RunStatus.QUEUED
    assert world["missions"].get_mission(running.id).status == MissionStatus.QUEUED
    assert world["runs"].get_run(waiting.id).status == RunStatus.WAITING_APPROVAL
    assert world["missions"].get_mission(waiting.id).status == MissionStatus.WAITING_APPROVAL


def test_overdue_task_is_one_open_alert_for_that_organization(world):
    client = world["client"]
    _register(client, "ada@example.com")
    _register(client, "bea@example.com")
    _login(client, "ada@example.com")
    project = client.post("/projects", json={"title": "Launch"})
    assert project.status_code == 200, project.text
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    task = client.post(
        f"/projects/{project.json()['id']}/tasks",
        json={"title": "File the brief", "deadline": past, "status": "open"},
    )
    assert task.status_code == 200, task.text
    assert detect_alerts() == 1

    listed = client.get("/alerts")
    assert listed.status_code == 200, listed.text
    alerts_json = listed.json()["alerts"]
    assert len(alerts_json) == 1
    assert alerts_json[0]["read"] is False
    assert "File the brief" in alerts_json[0]["summary"]

    _login(client, "bea@example.com")
    other = client.get("/alerts")
    assert other.status_code == 200, other.text
    assert other.json()["alerts"] == []
    assert client.post(f"/alerts/{alerts_json[0]['id']}/acknowledge").status_code == 404


def test_approve_and_reject_both_reach_the_graph(world):
    client = world["client"]
    ada = _register(client, "ada@example.com")
    org_id = world["orgs"].active_for_account(ada["id"])
    assert org_id
    approved = _waiting_run(
        world, user_id=ada["id"], organization_id=org_id, thread_id="thread-approve"
    )
    rejected = _waiting_run(
        world, user_id=ada["id"], organization_id=org_id, thread_id="thread-reject"
    )

    yes = client.post(f"/runs/{approved.id}/resume", json={"approved": True})
    assert yes.status_code == 200, yes.text
    no = client.post(f"/runs/{rejected.id}/resume", json={"approved": False})
    assert no.status_code == 200, no.text

    decisions = [call["input"].resume for call in world["graph"].calls]
    assert decisions == [{"approved": True}, {"approved": False}]
    assert world["graph"].sent == [{"approved": True}]


def test_feedback_is_on_the_run_and_a_second_edit_is_one_candidate(world, monkeypatch):
    client = world["client"]
    ada = _register(client, "ada@example.com")
    org_id = world["orgs"].active_for_account(ada["id"])
    assert org_id
    bea = _register(client, "bea@example.com")
    bea_org = world["orgs"].active_for_account(bea["id"])
    assert bea_org and bea_org != org_id

    def _run(user_id: str, organization_id: str, thread_id: str):
        run = world["runs"].create_run(
            instruction="Write the note",
            thread_id=thread_id,
            user_id=user_id,
            organization_id=organization_id,
        )
        world["runs"].update_status(run.id, RunStatus.COMPLETED, result_text="The brief is ready.")
        return run

    first = _run(ada["id"], org_id, "thread-one")
    second = _run(ada["id"], org_id, "thread-two")
    other = _run(bea["id"], bea_org, "thread-other")
    body = {"rating": -1, "note": "The date is missing.", "revision": "The date is missing."}

    async def _no_evals(*args, **kwargs):
        return []

    monkeypatch.setattr("improvement.propose.run_evals", _no_evals)
    from improvement.propose import propose

    _login(client, "ada@example.com")
    posted = client.post(f"/runs/{first.id}/feedback", json=body)
    assert posted.status_code == 200, posted.text
    visible = client.get(f"/runs/{first.id}")
    assert visible.status_code == 200, visible.text
    feedback = [step for step in visible.json()["steps"] if step["kind"] == "feedback"]
    assert len(feedback) == 1
    assert feedback[0]["data"]["revision"] == "The date is missing."
    assert propose(store=RunStore(world["db"]))["candidates"] == []

    again = client.post(f"/runs/{second.id}/feedback", json=body)
    assert again.status_code == 200, again.text
    _login(client, "bea@example.com")
    theirs = client.post(f"/runs/{other.id}/feedback", json=body)
    assert theirs.status_code == 200, theirs.text

    candidates = propose(store=RunStore(world["db"]))["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["organization_id"] == org_id
    assert set(candidates[0]["run_ids"]) == {first.id, second.id}
    assert other.id not in candidates[0]["run_ids"]


@pytest.mark.asyncio
async def test_weekly_report_uses_the_preset_and_names_only_this_organizations_task(world):
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    ours = world["projects"].create_project("org-a", "Launch", created_by="ada")
    theirs = world["projects"].create_project("org-b", "Secret program", created_by="bea")
    world["projects"].create_task(
        ours.id,
        organization_id="org-a",
        title="File the brief",
        created_by="ada",
        deadline=past,
        status="open",
    )
    world["projects"].create_task(
        theirs.id,
        organization_id="org-b",
        title="Other org secret",
        created_by="bea",
        deadline=past,
        status="open",
    )
    run = world["runs"].create_run(
        instruction="Write the weekly report",
        thread_id="thread-weekly",
        organization_id="org-a",
        user_id="ada",
    )
    script = _Script(
        [
            SpecialistAction(status="call_tool", tool="projects.search_tasks", tool_instruction="{}"),
            SpecialistAction(status="done", answer=""),
            SpecialistAction(
                status="done",
                answer="Completed work\n\nDelayed work\n\nRecommendations\n- No recommendations",
            ),
        ]
    )
    github_calls: list[tuple] = []
    google_calls: list[tuple] = []

    async def github_run(*args, **kwargs):
        github_calls.append(args)
        from tools.registry import ToolOutput

        return ToolOutput(text="No pull requests.", data={"items": []})

    async def google_request(self, *args, **kwargs):
        google_calls.append(args)
        return {}

    tasks = preset("Write the weekly report")
    assert [task["assignee_role"] for task in tasks] == ["project_agent", "report_writer"]
    token = current_mission_id.set(run.id)
    try:
        with (
            patch("tools.github.tool.run", github_run),
            patch("core.broker.executor.IntegrationExecutor._google_request", google_request),
            patch("httpx.AsyncClient", _NoNetwork),
            patch(
                "pipelines.coordinator_board.specialists.get_structured_llm",
                return_value=script,
            ),
            patch(
                "pipelines.coordinator_board.specialists.verify_task_output",
                new=AsyncMock(return_value=VerificationResult(passed=True, reasoning="ok")),
            ),
        ):
            planned = await coordinator_plan(
                {
                    "run_id": run.id,
                    "pipeline": "weekly_report",
                    "messages": [HumanMessage(content="Write the weekly report")],
                    "preset_tasks": tasks,
                }
            )
            ran = await specialists_fanout(
                {
                    **planned,
                    "run_id": run.id,
                    "messages": [HumanMessage(content="Write the weekly report")],
                }
            )
            with patch(
                "pipelines.coordinator_board.coordinator.get_llm",
                side_effect=RuntimeError("no model"),
            ):
                assembled = await coordinator_assemble({**planned, **ran, "run_id": run.id})
    finally:
        current_mission_id.reset(token)

    report = assembled["final_text"]
    assert "File the brief" in report
    assert "Other org secret" not in report
    assert github_calls == []
    assert google_calls == []
