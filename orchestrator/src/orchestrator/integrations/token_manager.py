"""Retrieve and refresh OAuth access tokens before tool execution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from orchestrator.integrations.oauth import OAuthService
from orchestrator.integrations.registry import get_integration
from orchestrator.integrations.store import IntegrationStore, StoredIntegration


class TokenManager:
    def __init__(
        self,
        store: IntegrationStore | None = None,
        oauth: OAuthService | None = None,
    ) -> None:
        self._store = store or IntegrationStore()
        self._oauth = oauth or OAuthService(self._store)

    def list_connected(self, user_id: str) -> list[str]:
        return self._store.list_connected(user_id)

    async def get_access_token(self, user_id: str, integration_id: str) -> str:
        record = self._store.get_tokens(user_id, integration_id)
        if not record:
            raise RuntimeError(f"{integration_id} is not connected for this user")
        if self._is_expired(record):
            refreshed = await self._refresh(record)
            return refreshed.access_token
        return record.access_token

    def is_connected(self, user_id: str, integration_id: str) -> bool:
        return self._store.is_connected(user_id, integration_id)

    def _is_expired(self, record: StoredIntegration) -> bool:
        if not record.expires_at:
            return False
        return record.expires_at <= datetime.now(timezone.utc) + timedelta(seconds=60)

    async def _refresh(self, record: StoredIntegration) -> StoredIntegration:
        spec = get_integration(record.integration)
        if not spec:
            raise RuntimeError(f"Unknown integration: {record.integration}")
        if spec["provider"] == "google":
            if not record.refresh_token:
                raise RuntimeError(f"Expired token for {record.integration}; reconnect required")
            tokens = await self._oauth.refresh_google_token(record.refresh_token)
            self._store.save_tokens(
                user_id=record.user_id,
                integration=record.integration,
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                expires_at=tokens.get("expires_at"),
            )
            updated = self._store.get_tokens(record.user_id, record.integration)
            if not updated:
                raise RuntimeError("Failed to persist refreshed token")
            return updated
        if record.expires_at and record.expires_at <= datetime.now(timezone.utc):
            raise RuntimeError(f"Token expired for {record.integration}; reconnect required")
        return record
