"""Prisma database client."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from prisma import Prisma

from app.config import get_settings

os.environ.setdefault("DATABASE_URL", get_settings().prisma_database_url())
prisma = Prisma()


async def connect_db() -> None:
    if not prisma.is_connected():
        await prisma.connect()


async def disconnect_db() -> None:
    if prisma.is_connected():
        await prisma.disconnect()


async def get_db() -> AsyncGenerator[Prisma, None]:
    yield prisma
