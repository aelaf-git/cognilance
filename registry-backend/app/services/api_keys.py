"""API key provisioning."""

from __future__ import annotations

from uuid import UUID

from prisma import Prisma
from prisma.models import ApiKey

from app.auth import _hash_key, generate_api_key


async def ensure_api_key(db: Prisma, *, raw_key: str, name: str = "bootstrap") -> UUID:
    prefix = raw_key[:12] if len(raw_key) >= 12 else raw_key
    existing = await db.apikey.find_first(where={"keyPrefix": prefix})
    if existing is not None:
        return UUID(existing.id)

    record = await db.apikey.create(
        data={
            "name": name,
            "keyPrefix": prefix,
            "keyHash": _hash_key(raw_key),
        }
    )
    return UUID(record.id)


async def create_api_key(db: Prisma, *, name: str) -> tuple[ApiKey, str]:
    full_key, prefix, key_hash = generate_api_key()
    record = await db.apikey.create(
        data={
            "name": name,
            "keyPrefix": prefix,
            "keyHash": key_hash,
        }
    )
    return record, full_key
