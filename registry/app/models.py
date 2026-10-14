"""SQLAlchemy models for the agent registry (replaces Prisma schema)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_visibility_online", "visibility", "online"),
        Index("ix_agents_last_heartbeat", "last_heartbeat"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    skills: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    visibility: Mapped[str] = mapped_column(String(64), default="public", nullable=False)
    tags: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    version: Mapped[str] = mapped_column(String(64), default="0.1.0", nullable=False)
    online: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )


class TraceEvent(Base):
    __tablename__ = "trace_events"
    __table_args__ = (
        Index("ix_trace_events_trace_id", "trace_id"),
        Index("ix_trace_events_trace_id_timestamp", "trace_id", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    event_type: Mapped[str] = mapped_column("type", String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    data: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class TraceIndex(Base):
    __tablename__ = "trace_index"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )
