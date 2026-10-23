"""Process-wide stores and helpers shared by API routers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import Request

from core.broker.oauth import OAuthService
from core.context.apps.store import init_all_stores
from core.context.conversations.store import ConversationStore
from core.context.request import current_user_id
from core.context.subscriptions.store import SubscriptionStore
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


def init_stores() -> None:
    mission_store.init_db()
    sub_store.init_db()
    run_store.init_db()
    board_store.init_db()
    init_all_stores()


def user_from(request: Request) -> str:
    return getattr(request.state, "user_id", current_user_id.get())


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
