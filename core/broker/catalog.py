"""Integration catalog: OAuth metadata and supported actions."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class IntegrationSpec(TypedDict):
    id: str
    name: str
    description: str
    provider: str
    scopes: list[str]
    actions: list[str]
    logo: str
    coming_soon: NotRequired[bool]


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
            "batch_update_document",
            "export_document",
            "insert_table",
            "insert_image",
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
        "coming_soon": True,
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
        "coming_soon": True,
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
        "coming_soon": True,
    },
    "x": {
        "id": "x",
        "name": "X",
        "description": "Draft and publish text posts to X (Twitter).",
        "provider": "x",
        "scopes": [
            "tweet.read",
            "tweet.write",
            "users.read",
            "offline.access",
        ],
        "actions": ["create_post", "get_me"],
        "logo": "x",
    },
    "reddit": {
        "id": "reddit",
        "name": "Reddit",
        "description": "Draft and submit text posts to a subreddit.",
        "provider": "reddit",
        "scopes": ["identity", "submit", "read"],
        "actions": ["submit_post", "get_me"],
        "logo": "reddit",
    },
    "linkedin": {
        "id": "linkedin",
        "name": "LinkedIn",
        "description": "Draft and publish text posts to your LinkedIn profile.",
        "provider": "linkedin",
        "scopes": ["openid", "profile", "w_member_social"],
        "actions": ["create_post", "get_me"],
        "logo": "linkedin",
    },
}


def list_integrations() -> list[IntegrationSpec]:
    return list(INTEGRATIONS.values())


def get_integration(integration_id: str) -> IntegrationSpec | None:
    return INTEGRATIONS.get(integration_id)


def integration_for_api(spec: IntegrationSpec, *, connected: bool) -> dict[str, Any]:
    coming_soon = bool(spec.get("coming_soon"))
    return {
        "id": spec["id"],
        "name": spec["name"],
        "description": spec["description"],
        "logo": spec["logo"],
        "connected": False if coming_soon else connected,
        "coming_soon": coming_soon,
        "auth_type": "oauth2",
        "actions": [] if coming_soon else spec["actions"],
    }
