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


def _is_proposal_task(query: str) -> bool:
    """True when the user wants a long-form proposal, report, RFP, or SOW Doc."""
    q = query.lower()
    proposal_terms = (
        "proposal",
        "rfp",
        "sow",
        "statement of work",
        "business report",
        "write a report",
        "create a report",
        "long-form",
        "long form",
    )
    if not _query_mentions(q, *proposal_terms):
        return False
    # Avoid hijacking inbox/email or pure Drive file listing.
    if _query_mentions(q, "email", "gmail", "inbox", "send mail"):
        return False
    return True


def _is_proposal_revise(query: str) -> bool:
    """True when the user is editing/expanding an existing proposal Doc section."""
    q = query.lower()
    if _query_mentions(q, "email", "gmail", "inbox", "send mail"):
        return False
    edit_verbs = (
        "edit",
        "revise",
        "expand",
        "rewrite",
        "update",
        "improve",
        "add more",
        "add detail",
        "more detail",
        "lengthen",
        "shorten",
        "fix",
        "change the",
        "change ",
        "make the",
        "make it",
        "justify",
        "justified",
        "align",
        "alignment",
    )
    section_hints = (
        "executive summary",
        "summary",
        "section",
        "scope",
        "pricing",
        "timeline",
        "milestone",
        "proposal",
        "introduction",
        "conclusion",
        "next steps",
        "why us",
        "findings",
        "recommendation",
        "document",
        "doc",
        "paragraph",
        "text",
    )
    if not _query_mentions(q, *edit_verbs):
        return False
    # Style-only asks ("make alignment justified") count as revise without a section name.
    if _query_mentions(
        q,
        "justify",
        "justified",
        "align",
        "alignment",
        "left",
        "center",
        "centre",
        "right",
    ):
        return True
    return _query_mentions(q, *section_hints) or _query_mentions(
        q, "document", "google doc", "the doc", "this doc"
    )


def _is_docs_create_task(query: str) -> bool:
    """True when the user wants a new (usually empty) Google Doc, not a proposal."""
    if _is_proposal_task(query):
        return False
    q = query.lower()
    if not is_google_docs_task(query) and not _query_mentions(
        q, "create a document", "new document", "blank doc", "empty doc"
    ):
        return False
    if not _query_mentions(
        q,
        "create",
        "new doc",
        "new document",
        "new google doc",
        "new google document",
        "make a",
        "make me",
        "blank",
        "empty",
    ):
        return False
    if _query_mentions(q, "write to", "append", "add to", "edit the", "update the"):
        return False
    return True


def _proposal_hire_subtask(query: str, *, title: str) -> Subtask:
    return {
        "id": "proposal-writer",
        "title": title,
        "instruction": query,
        "tool": "hire:proposal-writing",
        "skill": "proposal-writing",
        "assignee": "proposal-writing",
        "depends_on": [],
    }


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
    has_proposal_draft = DraftStore().has_proposal_draft(conv_id) if conv_id else False
    email_agent_available = has_agent_for_skill(catalog_agents or [], "email-writing")
    proposal_agent_available = has_agent_for_skill(
        catalog_agents or [], "proposal-writing"
    )
    docs_creator_available = has_agent_for_skill(catalog_agents or [], "docs-creating")

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
        if proposal_agent_available and (
            _is_proposal_task(query)
            or (has_proposal_draft and _is_proposal_revise(query))
        ):
            return [
                _proposal_hire_subtask(
                    query,
                    title=(
                        "Revise proposal / report in Google Docs"
                        if _is_proposal_revise(query)
                        else "Write proposal / report in Google Docs"
                    ),
                )
            ]
        # Pending proposal Doc + revise language: never fall through to append write_document.
        if proposal_agent_available and has_proposal_draft and _is_proposal_revise(query):
            return [
                _proposal_hire_subtask(
                    query, title="Revise proposal / report in Google Docs"
                )
            ]
        if docs_creator_available and _is_docs_create_task(query):
            return [
                {
                    "id": "docs-creator",
                    "title": "Create empty Google Doc",
                    "instruction": query,
                    "tool": "hire:docs-creating",
                    "skill": "docs-creating",
                    "assignee": "docs-creating",
                    "depends_on": [],
                }
            ]
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

    # Proposal/report even without explicit "Google Doc" wording when Drive + agent available.
    if (
        proposal_agent_available
        and client.is_connected(user_id, "google-drive")
        and (
            _is_proposal_task(query)
            or (has_proposal_draft and _is_proposal_revise(query))
        )
    ):
        return [
            _proposal_hire_subtask(
                query,
                title=(
                    "Revise proposal / report in Google Docs"
                    if _is_proposal_revise(query)
                    else "Write proposal / report in Google Docs"
                ),
            )
        ]

    if email_agent_available and client.is_connected(user_id, "gmail"):
        if has_pending_email and is_email_send_approval(query, has_pending_draft=True):
            return [
                {
                    "id": "email-writer",
                    "title": "Send approved email",
                    "instruction": query,
                    "tool": "hire:email-writing",
                    "skill": "email-writing",
                    "assignee": "email-writing",
                    "depends_on": [],
                }
            ]
        if is_email_compose_request(query):
            return [
                {
                    "id": "email-writer",
                    "title": "Compose or revise email",
                    "instruction": query,
                    "tool": "hire:email-writing",
                    "skill": "email-writing",
                    "assignee": "email-writing",
                    "depends_on": [],
                }
            ]

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
