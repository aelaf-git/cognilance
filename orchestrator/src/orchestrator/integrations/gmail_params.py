"""Email composition and send parameter preparation for Gmail."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from orchestrator.drafts.store import DraftStore
from orchestrator.integrations.project_context import project_context_for_composition
from orchestrator.llm import get_structured_llm, to_chat_messages

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_SUBJECT_RE = re.compile(r"subject\s*:\s*(.+)", re.IGNORECASE)
_QUOTE_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'|“([^”]+)”|‘([^’]+)’')

_SEND_APPROVAL_PHRASES = frozenset(
    {
        "send it",
        "send the email",
        "go ahead",
        "go ahead and send",
        "please send",
        "yes send",
        "good send",
        "looks good send",
        "approved",
        "approve",
        "do it",
        "send now",
    }
)


class EmailComposition(BaseModel):
    to: str | None = Field(default=None, description="Recipient email if known")
    subject: str = Field(description="Email subject line")
    body: str = Field(
        description="Full email body with greeting, paragraphs, and sign-off — NOT the user's command"
    )


def extract_emails(*texts: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for match in _EMAIL_RE.finditer(text or ""):
            addr = match.group(0).lower()
            if addr not in seen:
                seen.add(addr)
                found.append(match.group(0))
    return found


def _conversation_context(messages: list[BaseMessage] | None, limit: int = 12) -> str:
    if not messages:
        return ""
    recent = messages[-limit:]
    lines: list[str] = []
    for msg in to_chat_messages(recent):
        role = msg.get("role", "user")
        content = str(msg.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def _deterministic_email_params(
    instruction: str,
    params: dict[str, Any],
    conversation: list[BaseMessage] | None,
) -> dict[str, Any]:
    merged = dict(params)
    texts = [instruction]
    for msg in conversation or []:
        if isinstance(msg, HumanMessage):
            content = getattr(msg, "content", "") or ""
            if isinstance(content, str):
                texts.append(content)

    emails = extract_emails(*texts)
    if emails and not merged.get("to"):
        merged["to"] = emails[-1]

    for text in texts:
        if subj := _SUBJECT_RE.search(text):
            merged.setdefault("subject", subj.group(1).strip())
        for match in _QUOTE_RE.finditer(text):
            quoted = next((g for g in match.groups() if g), None)
            if quoted and len(quoted) > 20:
                merged.setdefault("body", quoted)
                break
    return merged


def _is_rate_limit_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "429" in message or "rate_limit" in message or "rate limit" in message


def _fallback_email_body(instruction: str, subject: str) -> str:
    lower = instruction.lower()
    greeting = "Hello,"
    if "mr." in lower or "mrs." in lower or "ms." in lower:
        greeting = "Dear Sir or Madam,"
    sign_off = "Best regards,\nCognilance"
    if "introduc" in lower:
        body = (
            f"{greeting}\n\n"
            "I wanted to take a moment to introduce myself and establish a connection. "
            "I look forward to getting to know you and exploring how we might work together.\n\n"
            f"{sign_off}"
        )
    elif "cognilance" in lower:
        from orchestrator.integrations.project_context import COGNILANCE_DESCRIPTION

        body = f"{greeting}\n\n{COGNILANCE_DESCRIPTION}\n\n{sign_off}"
    else:
        body = (
            f"{greeting}\n\n"
            f"I am writing regarding: {subject}\n\n"
            "Please let me know if you have any questions.\n\n"
            f"{sign_off}"
        )
    return body


async def compose_email_content(
    instruction: str,
    *,
    conversation: list[BaseMessage] | None = None,
    partial: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a full email draft using an LLM writer."""
    merged = _deterministic_email_params(instruction, dict(partial or {}), conversation)
    if merged.get("subject") and merged.get("body") and merged["body"] != instruction.strip():
        if len(str(merged["body"])) > 80:
            return merged

    context = _conversation_context(conversation)
    project_ctx = project_context_for_composition(instruction + " " + context)

    try:
        llm = get_structured_llm(EmailComposition, temperature=0.45)
        system = (
            "You are a professional email writer for Cognilance.\n"
            "Write a complete email: greeting, substantive body paragraphs, and sign-off.\n"
            "CRITICAL: `body` must be the actual email text — never repeat the user's command.\n"
            "If the user asks to introduce themselves, write a warm professional introduction.\n"
            "If the topic is Cognilance, explain what it is clearly using the project context.\n"
            "Keep tone professional but friendly. Sign off as Cognilance unless context suggests otherwise."
            f"{project_ctx}"
        )
        user_parts = [f"User request:\n{instruction}"]
        if context:
            user_parts.append(f"Conversation:\n{context}")
        if merged:
            user_parts.append(f"Partial fields:\n{merged}")

        result: EmailComposition = await llm.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ]
        )  # type: ignore[assignment]

        if result.to and not merged.get("to"):
            merged["to"] = result.to
        merged["subject"] = result.subject or merged.get("subject") or "Message from Cognilance"
        merged["body"] = result.body
    except Exception as exc:
        if not _is_rate_limit_error(exc):
            raise
        subject = str(merged.get("subject") or "Message from Cognilance")
        merged.setdefault("body", _fallback_email_body(instruction, subject))

    if not str(merged.get("subject", "")).strip():
        merged["subject"] = "Message from Cognilance"
    if not str(merged.get("body", "")).strip():
        merged["body"] = _fallback_email_body(instruction, merged["subject"])
    return merged


async def prepare_compose_email(
    instruction: str,
    params: dict[str, Any],
    *,
    conversation: list[BaseMessage] | None = None,
    conversation_id: str,
) -> dict[str, Any]:
    """Compose email, save pending draft, return payload for display."""
    composed = await compose_email_content(instruction, conversation=conversation, partial=params)
    DraftStore().save_email_draft(conversation_id, composed)
    return composed


async def prepare_send_email_params(
    instruction: str,
    params: dict[str, Any],
    *,
    conversation: list[BaseMessage] | None = None,
    conversation_id: str,
) -> dict[str, Any]:
    """Load pending draft and merge recipient; gate on approved draft."""
    store = DraftStore()
    draft = store.get_pending_email(conversation_id)
    if not draft:
        raise RuntimeError(
            "No pending email draft. Compose an email first and show it to the user for review."
        )

    merged = dict(draft)
    explicit = _deterministic_email_params(instruction, dict(params), conversation)

    to_addr = str(explicit.get("to") or merged.get("to") or "").strip()
    if not to_addr:
        emails = extract_emails(instruction)
        if emails:
            to_addr = emails[-1]
    if not to_addr:
        raise RuntimeError("Recipient email (to) is required to send.")

    merged["to"] = to_addr
    merged["subject"] = str(merged.get("subject") or explicit.get("subject") or "Message from Cognilance")
    merged["body"] = str(merged.get("body") or "")
    if not merged["body"].strip():
        raise RuntimeError("Pending email draft has no body.")

    return merged


def mark_email_draft_sent(conversation_id: str) -> None:
    """Mark pending draft as sent after Gmail API confirms delivery."""
    if conversation_id:
        DraftStore().mark_sent(conversation_id, "email")


_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_BREAK_RE = re.compile(r"</(?:p|div|h[1-6]|li|tr)>|<br\s*/?>", re.IGNORECASE)


def email_body_preview(body: str, *, max_chars: int = 220) -> str:
    """Plain-text preview of an email body — HTML stripped, whitespace collapsed."""
    text = _BLOCK_BREAK_RE.sub(" ", body)
    text = _TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars].rstrip() + "…"
    return text


def format_email_draft(payload: dict[str, Any]) -> str:
    """Short markdown summary — the email-draft card shows the full formatted email."""
    subject = str(payload.get("subject") or "(no subject)")
    to_addr = str(payload.get("to") or "").strip()
    preview = email_body_preview(str(payload.get("body") or ""))
    lines = [
        "Here's your email draft:",
        "",
        f"- **To:** {to_addr or '_add a recipient when you approve_'}",
        f"- **Subject:** {subject}",
    ]
    if preview:
        lines.append(f"- **Preview:** {preview}")
    notes = str(payload.get("format_notes") or "").strip()
    if notes:
        lines.append(f"- **Formatting:** {notes}")
    lines.extend(["", "Reply with your approval (and the recipient address if missing) to send."])
    return "\n".join(lines)


def format_send_email_result(payload: dict[str, Any]) -> str:
    message_id = str(payload.get("gmail_message_id") or payload.get("id") or "").strip()
    if not message_id:
        return (
            "The email was not sent — Gmail did not confirm delivery. "
            "Please try again or reconnect Gmail at /integrations."
        )
    subject = str(payload.get("subject") or "(no subject)")
    to_addr = str(payload.get("to") or "")
    preview = email_body_preview(str(payload.get("body") or payload.get("sent_body") or ""))
    lines = [
        f"Your email is on its way to **{to_addr}**.",
        "",
        f"- **Subject:** {subject}",
    ]
    if preview:
        lines.append(f"- **Preview:** {preview}")
    lines.extend(["", "If it doesn't show up in the inbox, check Spam or Promotions."])
    return "\n".join(lines)


def is_email_compose_request(query: str) -> bool:
    q = query.lower()
    if not any(term in q for term in ("email", "mail", "gmail")):
        return False
    return any(
        term in q
        for term in (
            "send",
            "compose",
            "write",
            "draft",
            "introduc",
            "email about",
            "mail about",
            "another email",
            "an email",
            "the email",
            "show me",
            "review",
            "let me review",
            "revise",
            "rewrite",
        )
    )


def is_email_send_approval(query: str, *, has_pending_draft: bool) -> bool:
    if not has_pending_draft:
        return False
    q = query.lower().strip().rstrip(".!")
    standalone_approvals = {
        "send",
        "please send",
        "send it",
        "send the email",
        "yes",
        "ok",
        "okay",
        "yep",
        "yeah",
        "approved",
        "approve",
        "go ahead",
        "do it",
        "send now",
    }
    if q in standalone_approvals:
        return True
    if extract_emails(query):
        if any(phrase in q for phrase in _SEND_APPROVAL_PHRASES):
            return True
        if len(q.split()) <= 12 and any(w in q for w in ("send", "good", "yes", "ok", "okay", "go ahead")):
            return True
    if any(phrase in q for phrase in _SEND_APPROVAL_PHRASES):
        return True
    return False
