"""LLM-assisted parameter extraction for Google Docs integration actions."""

from __future__ import annotations

import re
from typing import Any, Literal

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, Field

from orchestrator.integrations.project_context import COGNILANCE_DESCRIPTION, project_context_for_composition
from orchestrator.llm import get_structured_llm, to_chat_messages

_DOC_URL_RE = re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")
_QUOTE_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'|“([^”]+)”|‘([^’]+)’')
_DOC_CONTINUATION = frozenset(
    {
        "okay proceed",
        "proceed",
        "go ahead",
        "yes",
        "do it",
        "ok",
        "okay",
        "try again",
        "please do",
        "do that",
    }
)


class DocTextStyle(BaseModel):
    bold: bool | None = None
    font_size: float | None = Field(default=None, description="Font size in points, e.g. 72")
    font_family: str | None = Field(default=None, description="e.g. Times New Roman")


class GoogleDocActionParams(BaseModel):
    name: str | None = Field(default=None, description="Document title for create_document")
    content: str | None = Field(
        default=None,
        description="Body text to write — NOT the user's command, only the actual document text",
    )
    document_id: str | None = Field(
        default=None,
        description="Google Doc file id from a docs.google.com URL when updating an existing doc",
    )
    mode: Literal["append", "replace"] = "append"
    style: DocTextStyle | None = None


class DocumentContent(BaseModel):
    content: str = Field(
        description="Full document body text — substantive prose, not the user's command"
    )
    name: str | None = Field(default=None, description="Document title if not already set")


def extract_document_id(text: str) -> str | None:
    match = _DOC_URL_RE.search(text)
    return match.group(1) if match else None


def find_document_id_in_conversation(
    query: str,
    conversation: list[BaseMessage] | None,
) -> str | None:
    if doc_id := extract_document_id(query):
        return doc_id
    for msg in reversed(conversation or []):
        content = getattr(msg, "content", "") or ""
        if isinstance(content, str) and (doc_id := extract_document_id(content)):
            return doc_id
    return None


def _message_texts(
    conversation: list[BaseMessage] | None,
    *,
    instruction: str = "",
    users_only: bool = False,
) -> list[str]:
    texts: list[str] = []
    if instruction.strip():
        texts.append(instruction.strip())
    for msg in conversation or []:
        if users_only and not isinstance(msg, HumanMessage):
            continue
        content = getattr(msg, "content", "") or ""
        if isinstance(content, str) and content.strip():
            texts.append(content.strip())
    return texts


def _find_quoted_text(*texts: str) -> str | None:
    for text in texts:
        for match in _QUOTE_RE.finditer(text):
            quoted = next((g for g in match.groups() if g), None)
            if quoted and len(quoted) > 2:
                return quoted
    return None


def _extract_trailing_content(text: str) -> str | None:
    if ":" not in text:
        return None
    tail = text.rsplit(":", 1)[-1].strip().strip("\"'“”‘’")
    if not tail or tail.startswith("http") or len(tail) < 3:
        return None
    return tail


def _extract_style_from_text(text: str) -> dict[str, Any]:
    style: dict[str, Any] = {}
    lower = text.lower()
    if "bold" in lower:
        style["bold"] = True
    size_match = re.search(r"(?:size|font\s*size)\s*(\d+)", lower)
    if size_match:
        style["font_size"] = float(size_match.group(1))
    if "times new roman" in lower or "timesroman" in lower:
        style["font_family"] = "Times New Roman"
    return style


def _is_short_continuation(query: str) -> bool:
    q = query.lower().strip().rstrip(".")
    if q in _DOC_CONTINUATION:
        return True
    return bool(re.fullmatch(r"(yes|ok|please|thanks|thank you)( please)?", q))


def _query_mentions(query: str, *terms: str) -> bool:
    return any(term in query for term in terms)


def is_google_docs_task(
    query: str,
    conversation: list[BaseMessage] | None = None,
) -> bool:
    """True when the user wants to create or edit a Google Doc."""
    q = query.lower()
    if extract_document_id(query):
        return True
    if find_document_id_in_conversation(query, conversation) and (
        _is_short_continuation(query)
        or _query_mentions(
            q,
            "write",
            "add",
            "append",
            "bold",
            "font",
            "document",
            "same doc",
            "same document",
            "proceed",
            "link",
        )
    ):
        return True
    return _query_mentions(
        q,
        "google doc",
        "google docs",
        "gdoc",
        "google document",
        "create a doc",
        "new doc",
        "write a doc",
        "create document",
    )


def google_docs_action(
    query: str,
    conversation: list[BaseMessage] | None = None,
) -> Literal["create_document", "write_document"]:
    doc_id = find_document_id_in_conversation(query, conversation)
    q = query.lower()
    if doc_id:
        return "write_document"
    if _query_mentions(q, "create", "new doc", "new document") and not _query_mentions(
        q, "write to", "append", "add to"
    ):
        return "create_document"
    if _query_mentions(q, "write", "append", "add", "bold", "font", "edit", "update"):
        return "write_document"
    return "create_document"


def _fallback_create_content(instruction: str, name: str | None) -> str:
    lower = instruction.lower()
    title = name or "Document"
    if "cognilance" in lower:
        return f"{title}\n\n{COGNILANCE_DESCRIPTION}"
    if "goal" in lower or "summary" in lower:
        return (
            f"{title}\n\n"
            "Project Goals\n"
            "1. Build a reliable orchestrator that connects to user tools\n"
            "2. Let agents execute real tasks (email, calendar, documents)\n"
            "3. Add specialized marketplace agents for advanced workflows\n"
        )
    return (
        f"{title}\n\n"
        "This document was created by Cognilance based on your request. "
        "Add or edit sections as needed."
    )


async def compose_document_content(
    instruction: str,
    *,
    conversation: list[BaseMessage] | None = None,
    plan_context: str = "",
    name: str | None = None,
) -> str:
    """Write substantive document body text."""
    context = _conversation_context(conversation)
    project_ctx = project_context_for_composition(instruction + " " + context + " " + plan_context)
    try:
        llm = get_structured_llm(DocumentContent, temperature=0.5)
        system = (
            "You are a professional document writer for Cognilance.\n"
            "Write clear, substantive document content with headings and paragraphs as appropriate.\n"
            "CRITICAL: output only the document body — never repeat the user's command verbatim."
            f"{project_ctx}"
        )
        user_parts = [f"User request:\n{instruction}"]
        if plan_context.strip():
            user_parts.append(f"Planner context:\n{plan_context}")
        if context:
            user_parts.append(f"Conversation:\n{context}")
        if name:
            user_parts.append(f"Document title: {name}")
        result: DocumentContent = await llm.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ]
        )  # type: ignore[assignment]
        return result.content.strip() or _fallback_create_content(instruction, name)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            return _fallback_create_content(instruction, name)
        raise


def _is_rate_limit_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "429" in message or "rate_limit" in message or "rate limit" in message


def _params_need_enrichment(action: str, params: dict[str, Any], instruction: str) -> bool:
    instruction = instruction.strip()
    if action == "write_document":
        if not params.get("document_id"):
            return True
        content = str(params.get("content", "")).strip()
        if not content or content == instruction or _is_short_continuation(content):
            return True
        return False
    content = str(params.get("content", "")).strip()
    name = str(params.get("name", "")).strip()
    if not content or content == instruction:
        return True
    if not name or name in {"Cognilance Document", "Untitled"}:
        return True
    return False


def _deterministic_doc_params(
    action: str,
    instruction: str,
    conversation: list[BaseMessage] | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    doc_id = find_document_id_in_conversation(instruction, conversation)
    if doc_id:
        params["document_id"] = doc_id

    all_text = "\n".join(_message_texts(conversation, instruction=instruction))
    user_text = "\n".join(_message_texts(conversation, instruction=instruction, users_only=True))
    quoted = _find_quoted_text(instruction, user_text, all_text)
    if not quoted:
        for text in _message_texts(conversation, instruction=instruction, users_only=True):
            if trailing := _extract_trailing_content(text):
                quoted = trailing
                break
    if quoted:
        params["content"] = quoted

    style = _extract_style_from_text(all_text)
    if style:
        params["style"] = style

    if action == "write_document":
        params.setdefault("mode", "append")

    title_match = re.search(
        r"(?:called|named|titled)\s+[\"“']?([^\"”'\n]+)[\"”']?",
        user_text,
        re.IGNORECASE,
    )
    if title_match and action == "create_document":
        params["name"] = title_match.group(1).strip()

    return params


def _validate_write_params(params: dict[str, Any]) -> None:
    if not params.get("document_id"):
        raise RuntimeError(
            "Google Doc link required. Paste a docs.google.com/document/d/... URL."
        )
    if not str(params.get("content", "")).strip():
        raise RuntimeError(
            'Text to write is required. Put it in quotes, e.g. "Your text here".'
        )


async def prepare_google_doc_params(
    action: str,
    instruction: str,
    params: dict[str, Any],
    *,
    conversation: list[BaseMessage] | None = None,
    plan_context: str = "",
) -> dict[str, Any]:
    """Fill in Google Docs params: rules first, then LLM when needed."""
    merged = dict(params)
    locked_document_id = merged.get("document_id")

    deterministic = _deterministic_doc_params(action, instruction, conversation)
    for key, value in deterministic.items():
        if value and not merged.get(key):
            merged[key] = value

    if deterministic.get("document_id"):
        locked_document_id = deterministic["document_id"]
        merged["document_id"] = locked_document_id

    if not _params_need_enrichment(action, merged, instruction):
        if action == "write_document":
            _validate_write_params(merged)
        return merged

    content = str(merged.get("content", "")).strip()
    if not content or content == instruction.strip():
        composed = await compose_document_content(
            instruction,
            conversation=conversation,
            plan_context=plan_context,
            name=str(merged.get("name") or "") or None,
        )
        merged["content"] = composed

    try:
        context = _conversation_context(conversation)
        llm = get_structured_llm(GoogleDocActionParams, temperature=0)
        system = (
            "Extract structured parameters for a Google Docs API call.\n"
            "CRITICAL: `content` must be the actual text for the document — "
            "never repeat the user's command verbatim.\n"
            "For create_document: write the requested body (e.g. a goals summary).\n"
            "For write_document: extract only the text to add (often in quotes).\n"
            "If the user asks for bold/large/font styling, set style fields; do not use HTML.\n"
            "Copy document_id exactly from a docs.google.com URL — never invent one."
        )
        user_parts = [f"Action: {action}", f"User request:\n{instruction}"]
        if context:
            user_parts.append(f"Conversation:\n{context}")
        if merged:
            user_parts.append(f"Partial params:\n{merged}")

        result: GoogleDocActionParams = await llm.ainvoke(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ]
        )  # type: ignore[assignment]

        if result.name and not merged.get("name"):
            merged["name"] = result.name
        if result.content and (
            not merged.get("content") or merged.get("content") == instruction.strip()
        ):
            merged["content"] = result.content
        if result.document_id and not locked_document_id:
            merged["document_id"] = result.document_id
        if locked_document_id:
            merged["document_id"] = locked_document_id
        merged["mode"] = result.mode
        if result.style:
            style = dict(merged.get("style") or {})
            if result.style.bold is not None:
                style["bold"] = result.style.bold
            if result.style.font_size is not None:
                style["font_size"] = result.style.font_size
            if result.style.font_family:
                style["font_family"] = result.style.font_family
            if style:
                merged["style"] = style
    except Exception as exc:
        if not _is_rate_limit_error(exc):
            raise
        if action == "create_document":
            merged.setdefault("name", merged.get("name") or "Untitled")
            merged.setdefault(
                "content",
                _fallback_create_content(instruction, merged.get("name")),
            )

    if action == "write_document":
        if locked_document_id:
            merged["document_id"] = locked_document_id
        _validate_write_params(merged)
        return merged

    if not merged.get("name"):
        merged["name"] = "Untitled"
    if not str(merged.get("content", "")).strip():
        merged["content"] = _fallback_create_content(instruction, merged.get("name"))
    return merged


def _conversation_context(messages: list[BaseMessage] | None, limit: int = 16) -> str:
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
