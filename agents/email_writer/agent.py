"""Email Writer Agent — Groq + LangChain + CognilanceWorker."""

from __future__ import annotations

import os
import re
from pathlib import Path

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from proxy import OrchestratorProxyError, gmail_list, gmail_search, gmail_send

_AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(_AGENT_DIR / ".env")

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_SEND_PHRASES = (
    "send it",
    "send the email",
    "please send",
    "go ahead and send",
    "go ahead",
    "send now",
    "approved",
    "yes send",
    "please send!",
)

SYSTEM = """You write emails on behalf of the end user — never about yourself or Cognilance.
You receive their conversation history and optional prior draft. Behave like a careful human
using Gmail: clear prose, appropriate tone, and intentional formatting.

ROLE
- Write as the user (their voice, their ask). Never invent marketplace / email-writer self-intros.
- Infer length, tone, and structure from the conversation (e.g. three paragraphs, casual, formal).
- Extract recipient email when mentioned. Prefer revising a prior draft when one is provided;
  preserve its formatting unless the user asks to change style.

SUBJECT
- Plain text only (no HTML).

BODY (Gmail-ready HTML)
- `body` must be the actual email (greeting, paragraphs, sign-off) as HTML — never the user's
  command verbatim.
- Prefer one outer <div> wrapping the message; avoid full <html>/<body> documents.
- Default to light professional structure (<p>, <br>, optional mild emphasis) even when the user
  does not name a font.
- When the user asks for font, size, color, bold/italic/underline, lists, links, or alignment —
  apply them with inline CSS. Same when they imply style (e.g. "Times New Roman", "14pt",
  "blue headings", "larger title").

ALLOWED TAGS: p, br, div, span, strong, b, em, i, u, ul, ol, li, a, h1, h2, h3.
ALLOWED INLINE STYLES: font-family, font-size, color, text-align, line-height.
FORBIDDEN: script, iframe, form, remote tracking images, javascript: URLs.

format_notes: short human summary of styling applied (e.g. "Times New Roman 14pt, navy headings").
Leave empty if no special styling beyond basic paragraphs."""


class EmailDraft(BaseModel):
    to: str | None = Field(default=None, description="Recipient email if known")
    subject: str = Field(description="Plain-text email subject line (no HTML)")
    body: str = Field(
        description=(
            "Gmail-ready HTML email body with greeting, paragraphs, and sign-off. "
            "Use allowed tags and inline styles for font-family, font-size, color, etc."
        )
    )
    tone: str = Field(default="professional", description="Tone of the email")
    format_notes: str = Field(
        default="",
        description="Brief note on fonts/colors/layout applied, or empty if plain structure",
    )

worker = CognilanceWorker(
    name="Email Writer Agent",
    skills=["email-writing"],
    description="Composes, revises, and sends professional emails via orchestrator Gmail proxy.",
    tags=["worker", "langchain", "groq", "email", "automation"],
    port=8101,
)


def _llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    return ChatGroq(
        model=model,
        api_key=api_key,
        temperature=0.5,
    ).with_structured_output(EmailDraft)


def _extract_emails(text: str) -> list[str]:
    return _EMAIL_RE.findall(text or "")


def _wants_send(text: str) -> bool:
    q = text.lower().strip().rstrip(".!")
    if q in {"send", "please send", "yes", "ok", "okay", "approved", "approve"}:
        return True
    return any(p in text.lower() for p in _SEND_PHRASES)


def _is_pure_send_approval(text: str) -> bool:
    q = text.lower().strip().rstrip(".!")
    approvals = {
        "send",
        "please send",
        "send it",
        "send the email",
        "send now",
        "yes",
        "ok",
        "okay",
        "yep",
        "yeah",
        "approved",
        "approve",
        "go ahead",
        "do it",
        "yes send",
    }
    return q in approvals or (
        len(q.split()) <= 6 and any(p in q for p in ("send", "approve", "go ahead"))
    )


def _wants_list(text: str) -> bool:
    q = text.lower()
    return any(t in q for t in ("inbox", "list email", "recent email", "my emails"))


def _wants_search(text: str) -> bool:
    q = text.lower()
    return any(t in q for t in ("search email", "find email", "look for email"))


def _history_messages(history: list | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if not isinstance(history, list):
        return messages
    for item in history[-20:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if role not in {"user", "assistant", "system"}:
            role = "user"
        messages.append({"role": role, "content": content})
    return messages


async def _compose(
    instruction: str,
    *,
    prior: EmailDraft | None = None,
    history: list | None = None,
) -> EmailDraft:
    llm = _llm()
    msgs: list[dict[str, str]] = [{"role": "system", "content": SYSTEM}]
    msgs.extend(_history_messages(history))
    if prior:
        msgs.append(
            {
                "role": "user",
                "content": (
                    "Here is the current email draft to revise or finalize:\n"
                    f"To: {prior.to or '(unknown)'}\n"
                    f"Subject: {prior.subject}\n\n"
                    f"{prior.body}\n\n"
                    f"User request:\n{instruction}"
                ),
            }
        )
    else:
        msgs.append(
            {
                "role": "user",
                "content": (
                    "Compose the email the user asked for based on this conversation.\n"
                    f"Latest request:\n{instruction}"
                ),
            }
        )
    result = await llm.ainvoke(msgs)
    draft = result  # type: ignore[assignment]
    emails = _extract_emails(instruction)
    if history:
        for item in reversed(history):
            if isinstance(item, dict):
                emails.extend(_extract_emails(str(item.get("content") or "")))
    if emails and not draft.to:
        draft.to = emails[-1]
    if prior and not draft.to and prior.to:
        draft.to = prior.to
    return draft


def _output(
    draft: EmailDraft,
    *,
    status: str,
    gmail_message_id: str | None = None,
    extra: dict | None = None,
) -> dict:
    data = {
        "to": draft.to or "",
        "subject": draft.subject,
        "body": draft.body,
        "tone": draft.tone,
        "status": status,
        "gmail_message_id": gmail_message_id,
    }
    notes = (draft.format_notes or "").strip()
    if notes:
        data["format_notes"] = notes
    if extra:
        data.update(extra)
    return data


@worker.on_task
async def handle(task):
    text = task.input.text.strip()
    data = task.input.data or {}
    prior = data.get("prior_draft")
    history = data.get("conversation_history")

    task.think("Understanding email request with conversation context")

    if _wants_list(text):
        task.think("Fetching recent emails via orchestrator proxy")
        try:
            result = await gmail_list(data, max_results=10)
        except OrchestratorProxyError as exc:
            return task.fail(message=str(exc))
        emails = result.get("emails") or []
        summary = f"Found {len(emails)} recent email(s)."
        return task.complete(
            text=summary,
            data={"emails": emails, "count": len(emails), "status": "listed"},
        )

    if _wants_search(text):
        task.think("Searching inbox via orchestrator proxy")
        try:
            result = await gmail_search(data, query=text, max_results=10)
        except OrchestratorProxyError as exc:
            return task.fail(message=str(exc))
        return task.complete(
            text=f"Search completed for: {text}",
            data={**result, "status": "searched"},
        )

    prior_draft = None
    if isinstance(prior, dict) and prior.get("body"):
        prior_draft = EmailDraft(
            to=prior.get("to"),
            subject=str(prior.get("subject") or "Message"),
            body=str(prior["body"]),
            tone=str(prior.get("tone") or "professional"),
            format_notes=str(prior.get("format_notes") or ""),
        )

    # Pure send approval: use pending draft as-is — do not invent a new email.
    if _wants_send(text) and prior_draft and _is_pure_send_approval(text):
        draft = prior_draft
        task.think("Using pending draft from conversation — sending without rewrite")
    else:
        task.think("Composing email with Groq using full conversation context")
        try:
            draft = await _compose(text, prior=prior_draft, history=history)
        except Exception as exc:
            return task.fail(message=f"Composition failed: {exc}")

    if _wants_send(text):
        to_addr = (draft.to or "").strip()
        if not to_addr:
            emails = _extract_emails(text)
            if history:
                for item in reversed(history):
                    if isinstance(item, dict):
                        emails.extend(_extract_emails(str(item.get("content") or "")))
            to_addr = emails[-1] if emails else ""
        if not to_addr:
            return task.complete(
                text="Draft ready — provide a recipient email before sending.",
                data=_output(draft, status="draft"),
            )
        task.think(f"Sending to {to_addr} via orchestrator proxy")
        try:
            sent = await gmail_send(
                data,
                to=to_addr,
                subject=draft.subject,
                body=draft.body,
            )
        except OrchestratorProxyError as exc:
            return task.fail(message=str(exc))
        message_id = str(sent.get("gmail_message_id") or sent.get("id") or "")
        return task.complete(
            text=f"Email sent to {to_addr}.",
            data=_output(draft, status="sent", gmail_message_id=message_id or None),
        )

    return task.complete(
        text=f"Draft ready — subject: {draft.subject}",
        data=_output(draft, status="draft"),
    )


if __name__ == "__main__":
    worker.run()
