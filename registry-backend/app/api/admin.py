"""Admin endpoints for API key management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from prisma import Prisma

from app.auth import AuthContext, get_auth_context
from app.database import get_db
from app.schemas import CreateApiKeyRequest, CreateApiKeyResponse
from app.services.api_keys import create_api_key

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.post("/api-keys", response_model=CreateApiKeyResponse)
async def create_key(
    body: CreateApiKeyRequest,
    db: Prisma = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> CreateApiKeyResponse:
    if not auth.is_bootstrap:
        raise HTTPException(status_code=403, detail="Bootstrap API key required")
    record, full_key = await create_api_key(db, name=body.name)
    return CreateApiKeyResponse(
        id=UUID(record.id),
        name=record.name,
        key=full_key,
        prefix=record.keyPrefix,
    )
