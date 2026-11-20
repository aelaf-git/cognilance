"""Retrieve and refresh OAuth access tokens before tool execution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.broker.oauth import OAuthService
from core.broker.catalog import get_integration
from core.broker.store import IntegrationStore, StoredIntegration


def github_organization(user_id: str) -> str:
    """The run's organization when a mission is set, otherwise the caller's active one."""
    from core.context.request import current_mission_id

    mission_id = current_mission_id.get() or ""
    if mission_id:
        try:
            from core.runtime.runs.store import RunStore

            run = RunStore().get_run(mission_id)
            if run and run.organization_id:
                return run.organization_id
        except Exception:
            pass
        try:
            from core.runtime.missions.store import MissionStore

            mission = MissionStore().get_mission(mission_id)
            if mission and mission.organization_id:
                return mission.organization_id
        except Exception:
            pass
    from core.context.orgs.store import OrgStore

    return OrgStore().active_for_account(user_id) or ""


class TokenManager:
    def __init__(
        self,
        store: IntegrationStore | None = None,
        oauth: OAuthService | None = None,
    ) -> None:
        self._store = store or IntegrationStore()
        self._oauth = oauth or OAuthService(self._store)

    def list_connected(self, user_id: str) -> list[str]:
        names = [name for name in self._store.list_connected(user_id) if name != "github"]
        organization_id = github_organization(user_id)
        if organization_id and self._store.is_org_connected(organization_id, "github"):
            names.append("github")
        return names

    async def get_access_token(self, user_id: str, integration_id: str) -> str:
        record = self._record(user_id, integration_id)
        if not record:
            raise RuntimeError(f"{integration_id} is not connected for this user")
        if self._is_expired(record):
            refreshed = await self._refresh(record)
            return refreshed.access_token
        return record.access_token

    def is_connected(self, user_id: str, integration_id: str) -> bool:
        if integration_id == "github":
            organization_id = github_organization(user_id)
            return bool(
                organization_id and self._store.is_org_connected(organization_id, "github")
            )
        return self._store.is_connected(user_id, integration_id)

    def _record(self, user_id: str, integration_id: str) -> StoredIntegration | None:
        if integration_id == "github":
            organization_id = github_organization(user_id)
            if not organization_id:
                return None
            return self._store.get_org_grant(organization_id, integration_id)
        return self._store.get_tokens(user_id, integration_id)

    def _is_expired(self, record: StoredIntegration) -> bool:
        if not record.expires_at:
            return False
        return record.expires_at <= datetime.now(timezone.utc) + timedelta(seconds=60)

    async def _refresh(self, record: StoredIntegration) -> StoredIntegration:
        spec = get_integration(record.integration)
        if not spec:
            raise RuntimeError(f"Unknown integration: {record.integration}")
        provider = spec["provider"]
        refreshers = {
            "google": self._oauth.refresh_google_token,
            "x": self._oauth.refresh_x_token,
            "reddit": self._oauth.refresh_reddit_token,
            "linkedin": self._oauth.refresh_linkedin_token,
        }
        refresher = refreshers.get(provider)
        if refresher is not None:
            if not record.refresh_token:
                raise RuntimeError(f"Expired token for {record.integration}; reconnect required")
            tokens = await refresher(record.refresh_token)
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
