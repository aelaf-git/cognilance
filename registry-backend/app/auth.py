"""API key authentication."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import UUID

import bcrypt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prisma import Prisma

from app.config import get_settings
from app.database import get_db

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    api_key_id: UUID | None
    is_bootstrap: bool = False
    authenticated: bool = False


def _hash_key(raw_key: str) -> str:
    return bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()


def verify_key(raw_key: str, key_hash: str) -> bool:
    try:
        return bcrypt.checkpw(raw_key.encode(), key_hash.encode())
    except ValueError:
        return False


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, hash)."""
    suffix = secrets.token_urlsafe(24)
    full_key = f"ck-{suffix}"
    prefix = full_key[:12]
    return full_key, prefix, _hash_key(full_key)


async def _lookup_db_key(db: Prisma, raw_key: str):
    prefix = raw_key[:12] if len(raw_key) >= 12 else raw_key
    candidates = await db.apikey.find_many(where={"keyPrefix": prefix, "isActive": True})
    for candidate in candidates:
        if verify_key(raw_key, candidate.keyHash):
            return candidate
    return None


async def _resolve_key(db: Prisma, raw_key: str) -> AuthContext | None:
    record = await _lookup_db_key(db, raw_key)
    if record is not None:
        return AuthContext(api_key_id=UUID(record.id), authenticated=True)

    settings = get_settings()
    bootstrap = [k.strip() for k in settings.bootstrap_api_keys.split(",") if k.strip()]
    if raw_key in bootstrap:
        return AuthContext(api_key_id=None, is_bootstrap=True, authenticated=True)
    return None


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    db: Prisma = Depends(get_db),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    raw_key = credentials.credentials.strip()
    if not raw_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty API key")

    ctx = await _resolve_key(db, raw_key)
    if ctx is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return ctx


async def get_optional_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    db: Prisma = Depends(get_db),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return AuthContext(api_key_id=None, authenticated=False)

    raw_key = credentials.credentials.strip()
    if not raw_key:
        return AuthContext(api_key_id=None, authenticated=False)

    ctx = await _resolve_key(db, raw_key)
    return ctx or AuthContext(api_key_id=None, authenticated=False)
