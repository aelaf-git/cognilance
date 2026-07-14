"""Heuristic routing for connected integration actions."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage

from orchestrator.conversation.ack import is_acknowledgment
from orchestrator.integrations.client import IntegrationClient
from orchestrator.integrations.doc_params import google_docs_action, is_google_docs_task
from orchestrator.integrations.gmail_params import (
    is_email_compose_request,
    is_email_send_approval,
)
from orchestrator.drafts.store import DraftStore
from orchestrator.registry_cache import has_agent_for_skill
from orchestrator.integrations.calendar_params import prepare_calendar_list_params
from orchestrator.integrations.registry import INTEGRATIONS
from orchestrator.subscriptions.monitor_intent import (
    is_monitor_request,
    is_stop_monitor_request,
    monitor_integration_for_query,
)
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
    catalog_agents: list | None = None,
) -> list[Subtask] | None:
    """Return forced subtasks when a connected integration should run immediately."""
    from orchestrator.context import current_conversation_id

    conv_id = current_conversation_id.get() or ""
    has_pending_email = DraftStore().has_pending_email(conv_id) if conv_id else False
    email_agent_available = has_agent_for_skill(catalog_agents or [], "email-writing")

    if is_acknowledgment(query) and not has_pending_email:
        return None

    q = query.lower()

    if is_stop_monitor_request(query):
        integration = monitor_integration_for_query(query)
        if integration == "gmail" and client.is_connected(user_id, "gmail"):
            return [
                {
                    "id": "stop-monitor",
                    "title": "Stop inbox listener",
                    "instruction": query,
                    "tool": "app:gmail",
                    "action": "unsubscribe_inbox",
                    "params": {},
                    "assignee": "gmail",
                    "depends_on": [],
                }
            ]

    if is_monitor_request(query):
        from orchestrator.context import current_conversation_id
        from orchestrator.subscriptions.store import SubscriptionStore

        conv_id = current_conversation_id.get() or ""
        if conv_id and any(
            s.integration == "gmail" and s.kind == "new_email"
            for s in SubscriptionStore().list_active_for_conversation(conv_id)
        ):
            return None
        integration = monitor_integration_for_query(query)
        if integration == "gmail" and client.is_connected(user_id, "gmail"):
            return [
                {
                    "id": "gmail-monitor",
                    "title": "Listen for new Gmail messages",
                    "instruction": query,
                    "tool": "app:gmail",
                    "action": "subscribe_inbox",
                    "params": {"query": query},
                    "assignee": "gmail",
                    "depends_on": [],
                }
            ]

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

    if email_agent_available and client.is_connected(user_id, "gmail"):
        if has_pending_email and is_email_send_approval(query, has_pending_draft=True):
            return None
        if is_email_compose_request(query):
            return None

    if client.is_connected(user_id, "gmail") and has_pending_email:
        if is_email_send_approval(query, has_pending_draft=True):
            return [
                {
                    "id": "gmail-send",
                    "title": "Send approved email",
                    "instruction": query,
                    "tool": "app:gmail",
                    "action": "send_email",
                    "params": {},
                    "assignee": "gmail",
                    "depends_on": [],
                }
            ]

    if client.is_connected(user_id, "gmail") and is_email_compose_request(query):
        if is_email_send_approval(query, has_pending_draft=has_pending_email):
            return [
                {
                    "id": "gmail-send",
                    "title": "Send approved email",
                    "instruction": query,
                    "tool": "app:gmail",
                    "action": "send_email",
                    "params": {},
                    "assignee": "gmail",
                    "depends_on": [],
                }
            ]
        return [
            {
                "id": "gmail-compose",
                "title": "Compose email draft for review",
                "instruction": query,
                "tool": "app:gmail",
                "action": "compose_email",
                "params": {},
                "assignee": "gmail",
                "depends_on": [],
            }
        ]

    if client.is_connected(user_id, "gmail") and _query_mentions(
        q, "email", "emails", "inbox", "gmail", "mailbox", "mail"
    ):
        if is_monitor_request(query) or is_stop_monitor_request(query):
            return None
        if _query_mentions(q, "send", "compose", "write") and _query_mentions(
            q, "email", "mail"
        ):
            return None  # handled by compose_email routing above
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
        cal_params = prepare_calendar_list_params(query, {"max_results": 25}, user_id=user_id)
        return [
            {
                "id": "calendar",
                "title": "List calendar events",
                "instruction": query,
                "tool": "app:google-calendar",
                "action": "list_events",
                "params": cal_params,
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

    if (
        not INTEGRATIONS.get("slack", {}).get("coming_soon")
        and client.is_connected(user_id, "slack")
        and _query_mentions(q, "slack", "channel", "channels")
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

    if (
        not INTEGRATIONS.get("github", {}).get("coming_soon")
        and client.is_connected(user_id, "github")
        and _query_mentions(
            q, "github", "repository", "repositories", "repo", "repos", "pull request", "issues"
        )
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


def format_calendar_list_result(result: dict[str, Any]) -> str:
    events = result.get("events") or []
    if not events:
        window = ""
        if result.get("time_min") and result.get("time_max"):
            window = " in that time range"
        return f"No calendar events found{window}."

    lines = [f"Found {len(events)} calendar event(s):\n"]
    for i, event in enumerate(events, 1):
        title = event.get("summary") or "(no title)"
        start = event.get("start") or "unknown time"
        location = event.get("location") or ""
        lines.append(f"{i}. {title}")
        lines.append(f"   When: {start}")
        if location:
            lines.append(f"   Where: {location}")
        link = event.get("html_link") or ""
        if link:
            lines.append(f"   Link: {link}")
        lines.append("")
    return "\n".join(lines).strip()


def format_subscription_result(result: dict[str, Any]) -> str:
    if "stopped" in result:
        return str(result.get("message") or "Stopped.")
    if result.get("subscription_id"):
        if result.get("message"):
            return str(result["message"])
        if result.get("kind") == "recurring_task":
            return str(result.get("message") or "Recurring task scheduled.")
        interval = int(result.get("poll_interval_seconds") or 90)
        return (
            f"I'm listening for new Gmail messages and will check every {interval} seconds. "
            f"Say 'stop listening' whenever you want me to stop."
        )
    if result.get("message"):
        return str(result["message"])
    return str(result)


def format_recurring_result(result: dict[str, Any]) -> str:
    if result.get("message"):
        return str(result["message"])
    if "stopped" in result:
        return str(result.get("message") or "Stopped the recurring task.")
    return format_subscription_result(result)
