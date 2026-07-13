"""Integration catalog — OAuth metadata and supported actions."""

from __future__ import annotations

from typing import Any, TypedDict


class IntegrationSpec(TypedDict):
    id: str
    name: str
    description: str
    provider: str
    scopes: list[str]
    actions: list[str]
    logo: str


INTEGRATIONS: dict[str, IntegrationSpec] = {
    "google-drive": {
        "id": "google-drive",
        "name": "Google Drive",
        "description": "List, read, create, and upload files; create and edit Google Docs.",
        "provider": "google",
        "scopes": [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/documents",
        ],
        "actions": [
            "list_files",
            "read_file",
            "create_file",
            "upload_file",
            "create_document",
            "read_document",
            "write_document",
        ],
        "logo": "drive",
    },
    "gmail": {
        "id": "gmail",
        "name": "Gmail",
        "description": "Read, search, and send emails from your Gmail inbox.",
        "provider": "google",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
        ],
        "actions": [
            "list_emails",
            "read_email",
            "compose_email",
            "send_email",
            "search_emails",
            "subscribe_inbox",
            "unsubscribe_inbox",
            "check_inbox",
        ],
        "logo": "gmail",
    },
    "google-calendar": {
        "id": "google-calendar",
        "name": "Google Calendar",
        "description": "View, create, and delete calendar events.",
        "provider": "google",
        "scopes": ["https://www.googleapis.com/auth/calendar"],
        "actions": ["list_events", "create_event", "delete_event"],
        "logo": "calendar",
    },
    "notion": {
        "id": "notion",
        "name": "Notion",
        "description": "Query databases and create or update Notion pages.",
        "provider": "notion",
        "scopes": [],
        "actions": ["list_databases", "query_database", "create_page", "update_page"],
        "logo": "notion",
    },
    "slack": {
        "id": "slack",
        "name": "Slack",
        "description": "List channels, read messages, send messages, and search.",
        "provider": "slack",
        "scopes": [
            "channels:read",
            "channels:history",
            "chat:write",
            "search:read",
        ],
        "actions": ["list_channels", "read_messages", "send_message", "search_messages"],
        "logo": "slack",
    },
    "github": {
        "id": "github",
        "name": "GitHub",
        "description": "Browse repos, issues, pull requests, and read file contents.",
        "provider": "github",
        "scopes": ["repo", "read:user"],
        "actions": [
            "list_repositories",
            "list_issues",
            "create_issue",
            "list_pull_requests",
            "read_file",
        ],
        "logo": "github",
    },
}


def list_integrations() -> list[IntegrationSpec]:
    return list(INTEGRATIONS.values())


def get_integration(integration_id: str) -> IntegrationSpec | None:
    return INTEGRATIONS.get(integration_id)


def integration_for_api(spec: IntegrationSpec, *, connected: bool) -> dict[str, Any]:
    return {
        "id": spec["id"],
        "name": spec["name"],
        "description": spec["description"],
        "logo": spec["logo"],
        "connected": connected,
        "auth_type": "oauth2",
        "actions": spec["actions"],
    }
