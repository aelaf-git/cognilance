"""Email Writer Agent — Gemini + LangChain + CognilanceWorker."""

from __future__ import annotations

import os
import re
from pathlib import Path

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from proxy import OrchestratorProxyError, gmail_list, gmail_search, gmail_send

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

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
)

SYSTEM = """You are a professional email writer on the Cognilance marketplace.
Write complete emails with greeting, substantive body paragraphs, and sign-off.
CRITICAL: `body` must be the actual email text — never repeat the user's command verbatim.
Extract recipient email when mentioned. Use a clear, professional tone unless asked otherwise."""


class EmailDraft(BaseModel):
    to: str | None = Field(default=None, description="Recipient email if known")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Full email body with greeting and sign-off")
    tone: str = Field(default="professional", description="Tone of the email")


worker = CognilanceWorker(
    name="Email Writer Agent",
    skills=["email-writing"],
    description="Composes, revises, and sends professional emails via orchestrator Gmail proxy.",
    tags=["worker", "langchain", "gemini", "email", "automation"],
    port=8101,
)


def _llm():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is required")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=0.4,
    ).with_structured_output(EmailDraft)


def _extract_emails(text: str) -> list[str]:
    return _EMAIL_RE.findall(text or "")


def _wants_send(text: str) -> bool:
    q = text.lower().strip()
    return any(p in q for p in _SEND_PHRASES) or (q in {"send", "please send"})


def _wants_list(text: str) -> bool:
    q = text.lower()
    return any(t in q for t in ("inbox", "list email", "recent email", "my emails"))


def _wants_search(text: str) -> bool:
    q = text.lower()
    return any(t in q for t in ("search email", "find email", "look for email"))


async def _compose(instruction: str, *, prior: EmailDraft | None = None) -> EmailDraft:
    llm = _llm()
    user = instruction
    if prior:
        user = (
            f"Revise this email.\n\nOriginal:\nTo: {prior.to}\nSubject: {prior.subject}\n\n"
            f"{prior.body}\n\nRevision request:\n{instruction}"
        )
    result = await llm.ainvoke(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ]
    )
    draft = result  # type: ignore[assignment]
    emails = _extract_emails(instruction)
    if emails and not draft.to:
        draft.to = emails[-1]
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
    if extra:
        data.update(extra)
    return data


@worker.on_task
async def handle(task):
    text = task.input.text.strip()
    data = task.input.data or {}
    prior = data.get("prior_draft")

    task.think("Understanding email request")

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
        )

    task.think("Composing email with Gemini")
    try:
        draft = await _compose(text, prior=prior_draft)
    except Exception as exc:
        return task.fail(message=f"Composition failed: {exc}")

    if _wants_send(text):
        to_addr = (draft.to or "").strip()
        if not to_addr:
            emails = _extract_emails(text)
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
