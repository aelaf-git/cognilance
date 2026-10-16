"""LangGraph checkpointer shared by all durable pipelines (SQLite for now)."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from core.context.db import ensure_db_dir

_cm: AbstractAsyncContextManager[AsyncSqliteSaver] | None = None
_saver: AsyncSqliteSaver | None = None


def checkpoint_db_path() -> str:
    return str(ensure_db_dir().parent / "checkpoints.db")


async def get_checkpointer() -> AsyncSqliteSaver:
    """Open (once) and return the process-wide checkpointer."""
    global _cm, _saver
    if _saver is None:
        _cm = AsyncSqliteSaver.from_conn_string(checkpoint_db_path())
        _saver = await _cm.__aenter__()
    return _saver


async def close_checkpointer() -> None:
    global _cm, _saver
    if _cm is not None:
        await _cm.__aexit__(None, None, None)
    _cm = None
    _saver = None
