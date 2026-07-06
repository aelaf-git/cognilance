"""Heuristic routing for connected integration actions."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage

from orchestrator.integrations.client import IntegrationClient
from orchestrator.integrations.doc_params import google_docs_action, is_google_docs_task
from orchestrator.state import Subtask


def _query_mentions(query: str, *terms: str) -> bool:
    q = query.lower()
    return any(term in q for term in terms)


def integration_subtasks_for_query(
    query: str,
    client: IntegrationClient,
    user_id: str,
    *,
    conversation: list[BaseMessage] | None = None,
) -> list[Subtask] | None:
    """Return forced subtasks when a connected integration should run immediately."""
    q = query.lower()

    if client.is_connected(user_id, "google-drive") and is_google_docs_task(
        query, conversation
    ):
        action = google_docs_action(query, conversation)
        return [
            {
                "id": "google-docs",
                "title": "Create Google Doc" if action == "create_document" else "Update Google Doc",
                "instruction": query,
                "tool": "app:google-drive",
                "action": action,
                "params": {},
                "assignee": "google-drive",
                "depends_on": [],
            }
        ]

    if client.is_connected(user_id, "gmail") and _query_mentions(
        q, "email", "emails", "inbox", "gmail", "mailbox", "mail"
    ):
        if _query_mentions(q, "send", "compose", "write") and _query_mentions(
            q, "email", "mail"
        ):
            return None  # send needs structured params — let planner handle
        action = "search_emails" if _query_mentions(q, "search", "find") else "list_emails"
        params: dict[str, Any] = {"max_results": 10}
        if action == "search_emails":
            params["query"] = query
        return [
            {
                "id": "gmail",
                "title": "Check Gmail",
                "instruction": query,
                "tool": "app:gmail",
                "action": action,
                "params": params,
                "assignee": "gmail",
                "depends_on": [],
            }
        ]

    if client.is_connected(user_id, "google-calendar") and _query_mentions(
        q, "calendar", "event", "events", "meeting", "meetings", "schedule"
    ):
        return [
            {
                "id": "calendar",
                "title": "List calendar events",
                "instruction": query,
                "tool": "app:google-calendar",
                "action": "list_events",
                "params": {"max_results": 10},
                "assignee": "google-calendar",
                "depends_on": [],
            }
        ]

    if client.is_connected(user_id, "google-drive") and _query_mentions(
        q, "drive", "google drive", "my files"
    ):
        return [
            {
                "id": "drive",
                "title": "List Drive files",
                "instruction": query,
                "tool": "app:google-drive",
                "action": "list_files",
                "params": {"page_size": 15},
                "assignee": "google-drive",
                "depends_on": [],
            }
        ]

    if client.is_connected(user_id, "slack") and _query_mentions(
        q, "slack", "channel", "channels"
    ):
        return [
            {
                "id": "slack",
                "title": "List Slack channels",
                "instruction": query,
                "tool": "app:slack",
                "action": "list_channels",
                "params": {},
                "assignee": "slack",
                "depends_on": [],
            }
        ]

    if client.is_connected(user_id, "github") and _query_mentions(
        q, "github", "repository", "repositories", "repo", "repos", "pull request", "issues"
    ):
        return [
            {
                "id": "github",
                "title": "List GitHub repositories",
                "instruction": query,
                "tool": "app:github",
                "action": "list_repositories",
                "params": {},
                "assignee": "github",
                "depends_on": [],
            }
        ]

    return None


def format_document_result(result: dict[str, Any]) -> str:
    name = result.get("name") or result.get("title") or "Google Doc"
    url = result.get("url") or ""
    document_id = result.get("document_id") or result.get("id") or ""
    if not url and document_id:
        url = f"https://docs.google.com/document/d/{document_id}/edit"

    if result.get("text") is not None:
        preview = str(result.get("text", ""))[:500]
        lines = [f'Read document "{name}".']
        if url:
            lines.append(f"Open: {url}")
        if preview:
            lines.append(f"\nContent preview:\n{preview}")
        return "\n".join(lines)

    if result.get("chars_written"):
        lines = [
            f'Updated Google Doc ({result.get("mode", "append")} mode).',
            f"Characters written: {result['chars_written']}",
        ]
        if result.get("styled"):
            lines.append("Text formatting was applied via the Google Docs API.")
        if url:
            lines.append(f"Open: {url}")
        return "\n".join(lines)

    lines = [f'Created Google Doc "{name}".']
    if result.get("content_written"):
        lines.append("Document body was written (not the raw user command).")
    if result.get("styled"):
        lines.append("Text formatting was applied via the Google Docs API.")
    if url:
        lines.append(f"Open: {url}")
    return "\n".join(lines)


def format_gmail_list_result(result: dict[str, Any]) -> str:
    emails = result.get("emails") or []
    if not emails:
        return "No emails found in your inbox."
    lines = [f"Here are your {len(emails)} most recent emails:\n"]
    for i, email in enumerate(emails, 1):
        subject = email.get("subject") or "(no subject)"
        sender = email.get("from") or "Unknown sender"
        date = email.get("date") or ""
        snippet = email.get("snippet") or ""
        lines.append(f"{i}. {subject}")
        lines.append(f"   From: {sender}")
        if date:
            lines.append(f"   Date: {date}")
        if snippet:
            lines.append(f"   Preview: {snippet[:120]}")
        lines.append("")
    return "\n".join(lines).strip()
