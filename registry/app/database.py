"""SQLAlchemy async database session (SQLite via aiosqlite)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def to_async_database_url(url: str) -> str:
    """Normalize Prisma-style `file:` / `sqlite:` URLs to SQLAlchemy aiosqlite."""
    raw = (url or "").strip()
    if raw.startswith("sqlite+aiosqlite://"):
        return raw
    if raw.startswith("file:"):
        path = raw[5:]
        if path.startswith("//"):
            path = path[2:]
        return f"sqlite+aiosqlite:///{path}"
    if raw.startswith("sqlite:///"):
        return "sqlite+aiosqlite:///" + raw[len("sqlite:///") :]
    if "://" not in raw:
        return f"sqlite+aiosqlite:///{raw}"
    return raw


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        db_url = to_async_database_url(settings.database_url)
        if db_url.startswith("sqlite+aiosqlite:///"):
            path = db_url[len("sqlite+aiosqlite:///") :]
            if path and path != ":memory:":
                Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def connect_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def disconnect_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def session_scope() -> AsyncSession:
    """Open a short-lived session for background tasks."""
    return get_session_factory()()
