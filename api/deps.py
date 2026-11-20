"""Process-wide stores and helpers shared by API routers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from core.broker.oauth import OAuthService
from core.context.apps.store import init_all_stores
from core.context.conversations.store import ConversationStore
from core.context.orgs.store import ROLE_RANK, Membership, OrgStore
from core.context.projects.store import ProjectStore
from core.context.request import current_user_id
from core.context.subscriptions.store import SubscriptionStore
from core.context.users.accounts import AccountStore
from core.runtime.board.store import BoardStore
from core.runtime.missions.store import MissionStore
from core.runtime.runs.store import RunStore

STATIC_DIR = Path(__file__).resolve().parent / "static"

mission_store = MissionStore()
conv_store = ConversationStore()
sub_store = SubscriptionStore()
run_store = RunStore()
board_store = BoardStore()
oauth_service = OAuthService()
account_store = AccountStore()
org_store = OrgStore()
project_store = ProjectStore()


def init_stores() -> None:
    mission_store.init_db()
    sub_store.init_db()
    run_store.init_db()
    board_store.init_db()
    account_store.init_db()
    org_store.init_db()
    project_store.init_db()
    init_all_stores()


def user_from(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None) or current_user_id.get()
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return str(user_id)


def active_organization_id(account_id: str) -> str | None:
    return org_store.active_for_account(account_id)


def owner_filter(account_id: str) -> dict[str, str]:
    """Org membership scopes reads. Accounts without one stay on user_id."""
    org_id = active_organization_id(account_id)
    if org_id:
        return {"organization_id": org_id}
    return {"user_id": account_id}


def organization_ids_for(account_id: str) -> list[str]:
    return [membership.organization_id for membership in org_store.memberships_for(account_id)]


def can_read_conversation(account_id: str, conversation) -> bool:
    """An organization conversation is shared with every membership. A private one stays with its user."""
    if conversation is None or not account_id:
        return False
    organization_id = getattr(conversation, "organization_id", None)
    if organization_id:
        return org_store.membership_for(account_id, organization_id) is not None
    owner = getattr(conversation, "user_id", None)
    return bool(owner) and owner == account_id


def account_display_name(account_id: str) -> str | None:
    account = account_store.get_by_id(account_id)
    if account is None:
        return None
    name = str(account.display_name or "").strip()
    return name or None


def require_membership(
    account_id: str,
    organization_id: str,
    minimum: str = "member",
) -> Membership:
    """Hide a missing organization or membership. A low role is forbidden."""
    if org_store.get_organization(organization_id) is None:
        raise HTTPException(status_code=404, detail="Not found")
    membership = org_store.membership_for(account_id, organization_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Not found")
    if ROLE_RANK.get(membership.role, 0) < ROLE_RANK[minimum]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return membership


def thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


# In-flight chat/mission graph tasks: abort cancels these so work stops mid-run.
_running_mission_tasks: dict[str, asyncio.Task[Any]] = {}


def register_mission_task(mission_id: str, task: asyncio.Task[Any]) -> None:
    _running_mission_tasks[mission_id] = task

    def _cleanup(done: asyncio.Task[Any]) -> None:
        if _running_mission_tasks.get(mission_id) is done:
            _running_mission_tasks.pop(mission_id, None)

    task.add_done_callback(_cleanup)


def cancel_mission_task(mission_id: str) -> bool:
    task = _running_mission_tasks.get(mission_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True
