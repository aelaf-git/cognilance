"""OAuth2 authorization and token exchange."""

from __future__ import annotations

import base64
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from orchestrator.integrations.registry import get_integration
from orchestrator.integrations.store import IntegrationStore


def public_base_url() -> str:
    return os.getenv("ORCHESTRATOR_PUBLIC_URL", "http://127.0.0.1:8200").rstrip("/")


def callback_url() -> str:
    return f"{public_base_url()}/integrations/oauth/callback"


class OAuthService:
    def __init__(self, store: IntegrationStore | None = None) -> None:
        self._store = store or IntegrationStore()
        self._store.init_db()

    def start_oauth(self, user_id: str, integration_id: str) -> str:
        spec = get_integration(integration_id)
        if not spec:
            raise ValueError(f"Unknown integration: {integration_id}")
        state = secrets.token_urlsafe(32)
        self._store.save_oauth_state(state, user_id, integration_id)
        provider = spec["provider"]
        if provider == "google":
            return self._google_auth_url(integration_id, spec["scopes"], state)
        if provider == "github":
            return self._github_auth_url(spec["scopes"], state)
        if provider == "slack":
            return self._slack_auth_url(spec["scopes"], state)
        if provider == "notion":
            return self._notion_auth_url(state)
        raise ValueError(f"Unsupported provider: {provider}")

    async def handle_callback(self, code: str, state: str) -> tuple[str, str]:
        resolved = self._store.pop_oauth_state(state)
        if not resolved:
            raise ValueError("Invalid or expired OAuth state")
        user_id, integration_id = resolved
        spec = get_integration(integration_id)
        if not spec:
            raise ValueError(f"Unknown integration: {integration_id}")
        provider = spec["provider"]
        if provider == "google":
            tokens = await self._exchange_google(code)
        elif provider == "github":
            tokens = await self._exchange_github(code)
        elif provider == "slack":
            tokens = await self._exchange_slack(code)
        elif provider == "notion":
            tokens = await self._exchange_notion(code)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self._store.save_tokens(
            user_id=user_id,
            integration=integration_id,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_at=tokens.get("expires_at"),
        )
        return user_id, integration_id

    def disconnect(self, user_id: str, integration_id: str) -> None:
        self._store.disconnect(user_id, integration_id)

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        connected = set(self._store.list_connected(user_id))
        from orchestrator.integrations.registry import integration_for_api, list_integrations

        return [
            integration_for_api(spec, connected=spec["id"] in connected)
            for spec in list_integrations()
        ]

    def _google_client(self) -> tuple[str, str]:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
        return client_id, client_secret

    def _google_auth_url(self, integration_id: str, scopes: list[str], state: str) -> str:
        client_id, _ = self._google_client()
        params = {
            "client_id": client_id,
            "redirect_uri": callback_url(),
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    async def _exchange_google(self, code: str) -> dict[str, Any]:
        client_id, client_secret = self._google_client()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": callback_url(),
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            data = response.json()
        expires_at = None
        if data.get("expires_in"):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "expires_at": expires_at,
        }

    async def refresh_google_token(self, refresh_token: str) -> dict[str, Any]:
        client_id, client_secret = self._google_client()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()
        expires_at = None
        if data.get("expires_in"):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token") or refresh_token,
            "expires_at": expires_at,
        }

    def _github_auth_url(self, scopes: list[str], state: str) -> str:
        client_id = os.getenv("GITHUB_CLIENT_ID", "")
        if not client_id:
            raise RuntimeError("GITHUB_CLIENT_ID must be set")
        params = {
            "client_id": client_id,
            "redirect_uri": callback_url(),
            "scope": " ".join(scopes),
            "state": state,
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    async def _exchange_github(self, code: str) -> dict[str, Any]:
        client_id = os.getenv("GITHUB_CLIENT_ID", "")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise RuntimeError("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET must be set")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": callback_url(),
                },
            )
            response.raise_for_status()
            data = response.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": None,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=365),
        }

    def _slack_auth_url(self, scopes: list[str], state: str) -> str:
        client_id = os.getenv("SLACK_CLIENT_ID", "")
        if not client_id:
            raise RuntimeError("SLACK_CLIENT_ID must be set")
        params = {
            "client_id": client_id,
            "redirect_uri": callback_url(),
            "scope": ",".join(scopes),
            "state": state,
        }
        return f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"

    async def _exchange_slack(self, code: str) -> dict[str, Any]:
        client_id = os.getenv("SLACK_CLIENT_ID", "")
        client_secret = os.getenv("SLACK_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise RuntimeError("SLACK_CLIENT_ID and SLACK_CLIENT_SECRET must be set")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": callback_url(),
                },
            )
            response.raise_for_status()
            data = response.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "Slack OAuth failed"))
        token = data.get("access_token") or data.get("authed_user", {}).get("access_token")
        return {
            "access_token": token,
            "refresh_token": data.get("refresh_token"),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=365),
        }

    def _notion_auth_url(self, state: str) -> str:
        client_id = os.getenv("NOTION_CLIENT_ID", "")
        if not client_id:
            raise RuntimeError("NOTION_CLIENT_ID must be set")
        params = {
            "client_id": client_id,
            "redirect_uri": callback_url(),
            "response_type": "code",
            "owner": "user",
            "state": state,
        }
        return f"https://api.notion.com/v1/oauth/authorize?{urlencode(params)}"

    async def _exchange_notion(self, code: str) -> dict[str, Any]:
        client_id = os.getenv("NOTION_CLIENT_ID", "")
        client_secret = os.getenv("NOTION_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise RuntimeError("NOTION_CLIENT_ID and NOTION_CLIENT_SECRET must be set")
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.notion.com/v1/oauth/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json",
                },
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": callback_url(),
                },
            )
            response.raise_for_status()
            data = response.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": None,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=365),
        }
