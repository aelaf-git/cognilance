"""Chat/result presenters for integration and tool outputs."""

from __future__ import annotations

from typing import Any

def format_document_result(result: dict[str, Any]) -> str:
    name = result.get("name") or result.get("title") or "Google Doc"
    url = result.get("url") or ""
    document_id = result.get("document_id") or result.get("id") or ""
    if not url and document_id:
        url = f"https://docs.google.com/document/d/{document_id}/edit"

    status = str(result.get("status") or "")
    message = str(result.get("message") or "").strip()

    # Style/alignment outcomes: prefer the agent's explicit message (incl. already-applied).
    if status in {"already_applied", "applied"} or (
        result.get("alignment") and message and status in {"published", "already_applied", "applied"}
    ):
        lines = [message] if message else [
            f'Alignment update on "{name}" ({status or "applied"}).'
        ]
        if url and status != "already_applied":
            lines.append(f"Open: {url}")
        return "\n".join(lines)

    if status == "created":
        lines = [f'Created empty Google Doc "{name}".']
        if url:
            lines.append(f"Open: {url}")
        return "\n".join(lines)

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

    if result.get("request_count") and result.get("document_id") and not result.get("alignment"):
        lines = [
            f'Applied {result["request_count"]} Google Docs formatting update(s).',
        ]
        if result.get("title") or result.get("name"):
            lines.insert(
                0,
                f'Published Google Doc "{result.get("title") or result.get("name")}".',
            )
        if url:
            lines.append(f"Open: {url}")
        return "\n".join(lines)

    if result.get("text_preview") is not None and result.get("mime_type"):
        preview = str(result.get("text_preview") or "")[:500]
        lines = [f'Exported Google Doc ({result.get("mime_type")}).']
        if url:
            lines.append(f"Open: {url}")
        if preview:
            lines.append(f"\nContent preview:\n{preview}")
        return "\n".join(lines)

    if status in {"published", "draft", "preview"} and (
        result.get("title") or result.get("sections")
    ):
        title = result.get("title") or "Proposal"
        if status == "draft":
            lines = [f'Draft ready — "{title}".']
        elif status == "preview":
            lines = [f'Preview of "{title}".']
        else:
            lines = [f'Published Google Doc "{title}".']
        if url:
            lines.append(f"Open: {url}")
        notes = str(result.get("format_notes") or "").strip()
        if notes:
            lines.append(f"Formatting: {notes}")
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
