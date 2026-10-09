"""Proposal Writer Agent — Groq + LangChain + CognilanceWorker + Google Docs proxy."""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from charts import chart_to_png
from doc_structure import (
    ALIGNMENT_JUSTIFIED,
    all_aligned,
    alignment_summary,
    alignment_update_requests,
    find_section,
    normalize_alignment,
    paragraphs_in_section,
    parse_paragraphs,
    parse_sections,
    sections_outline,
)
from docs_ir import (
    DeferredInsert,
    ProposalDraft,
    ProposalSection,
    body_text_requests,
    clear_body_requests,
    closing_text_requests,
    delete_range_requests,
    draft_to_batch_requests,
    sanitize_body_text,
    section_deferred,
    section_text_requests,
)
from proxy import (
    OrchestratorProxyError,
    docs_batch_update,
    docs_create,
    docs_export,
    docs_insert_image,
    docs_insert_table,
    docs_read,
)

_AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(_AGENT_DIR / ".env")

_DOC_URL_RE = re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")

SYSTEM = """You write professional long-form proposals and reports on behalf of the end user.
You receive their conversation and optional prior draft. Produce a complete, client-ready
document structure — never meta commentary about Cognilance or yourself.

ROLE
- Write as the user's firm / consultant / analyst voice.
- Cover proposals, RFPs, SOWs, and business/research reports.
- Infer client name, scope, timeline, pricing, and metrics when mentioned.
- Prefer revising a prior draft when one is provided; keep document_id if present.
- Default proposal sections when vague: Executive Summary, Understanding of Needs,
  Proposed Solution, Scope of Work, Timeline & Milestones, Investment / Pricing,
  Why Us, Next Steps (also mirror into `closing` if useful).
- Default report sections when vague: Executive Summary, Findings, Analysis,
  Recommendations, Appendix.

LAYOUT — CRITICAL (Google Docs, not Markdown)
- Professional, confident, concise. No filler.
- NEVER use Markdown: no # ## ### headings, no **bold**, no *italic*, no `code`,
  no | tables |, no ``` fences. Headings are separate fields; Docs applies styles.
- Section `body`: plain paragraphs separated by blank lines.
- Bullets MUST be lines starting with "- " only (not *, •, or numbered markdown).
- Use `level` 1–3 for heading hierarchy (H1/H2/H3).
- Pricing or comparison data → native `table` (headers + string rows).
- Numeric series the user provides → `chart` (bar/line/pie) with labels + values.
  Never invent chart numbers; only chart data present in the conversation.
- Images: only set `image.url` or `image.drive_file_id` when the user provides one.
  Never invent or generate images.
- `page_break_before` sparingly for major section breaks.
- `title`: short document title (not the user's raw command).
- `format_notes`: brief layout summary (e.g. "Georgia headings, pricing table, bar chart").

Do not invent fake legal claims. If pricing is unknown, use placeholder ranges clearly marked.
"""

SECTION_PATCH_SYSTEM = """You surgically edit ONE section of an existing Google Doc proposal/report.
The live document is the source of truth. Other sections must remain unchanged.

RULES
- Return ONLY the replacement body for the targeted section (not the whole document).
- Keep the existing section heading; do not repeat the heading inside `body`.
- Expand, revise, or rewrite that section per the user request.
- Preserve facts from the current body unless the user asks to change them.
- NEVER use Markdown: no # headings, no **, no *, no | tables |, no ```.
  Plain paragraphs with blank lines; bullets as lines starting with "- " only.
- `section_heading` must match an existing heading from the outline (or closest match).
- `format_notes`: short note on what changed.
"""


class SectionPatch(BaseModel):
    section_heading: str = Field(
        description="Exact or closest existing Doc heading to replace (e.g. Executive Summary)"
    )
    body: str = Field(
        description=(
            "Replacement section body only. Plain paragraphs and '- ' bullets. "
            "No markdown headings or emphasis markers."
        )
    )
    format_notes: str = Field(
        default="",
        description="Brief note on the edit applied",
    )


class StylePatch(BaseModel):
    alignment: str = Field(
        description="Docs alignment: START, CENTER, END, or JUSTIFIED"
    )
    scope: str = Field(
        default="document",
        description="document = whole Doc; section = one named section",
    )
    section_heading: str = Field(
        default="",
        description="When scope=section, the heading to restyle",
    )


_ALIGNMENT_LABELS = {
    "START": "left",
    "CENTER": "center",
    "END": "right",
    "JUSTIFIED": "justified",
}


def _extract_alignment(text: str) -> str | None:
    """Deterministic alignment from user text. Returns Docs enum or None."""
    q = text.lower()
    if re.search(r"\bjustif(?:y|ied|ication)\b", q):
        return ALIGNMENT_JUSTIFIED
    if re.search(r"\balign(?:ment|ed)?\b.*\b(left|start)\b", q) or re.search(
        r"\b(left|start)[-\s]?align", q
    ):
        return "START"
    if re.search(r"\balign(?:ment|ed)?\b.*\b(center|centre)\b", q) or re.search(
        r"\b(center|centre)[-\s]?align", q
    ):
        return "CENTER"
    if re.search(r"\balign(?:ment|ed)?\b.*\b(right|end)\b", q) or re.search(
        r"\b(right|end)[-\s]?align", q
    ):
        return "END"
    if re.search(r"\b(left|start)\s+alignment\b", q):
        return "START"
    if re.search(r"\b(center|centre)\s+alignment\b", q):
        return "CENTER"
    if re.search(r"\b(right|end)\s+alignment\b", q):
        return "END"
    # "make the alignment justified" already covered; bare "make it centered"
    if re.search(r"\b(center|centre)(?:ed)?\b", q) and re.search(
        r"\b(align|alignment|text|document|doc|section|paragraph)\b", q
    ):
        return "CENTER"
    if re.search(r"\bleft\b", q) and re.search(
        r"\b(align|alignment|text|document|doc|section|paragraph)\b", q
    ):
        return "START"
    if re.search(r"\bright\b", q) and re.search(
        r"\b(align|alignment|text|document|doc|section|paragraph)\b", q
    ):
        return "END"
    return None


def _wants_style_edit(text: str) -> bool:
    return _extract_alignment(text) is not None


def _style_scope_is_section(text: str, sections: list) -> str:
    """Return section heading if user scoped to a section, else ''."""
    q = text.lower()
    if re.search(r"\b(whole|entire|full)\s+(document|doc|proposal|report)\b", q):
        return ""
    if re.search(r"\b(the\s+)?(document|doc|proposal|report)\b", q) and not any(
        sec.heading.lower() in q for sec in sections
    ):
        # "justify the document" → whole doc
        if re.search(r"\b(justify|align|alignment)\b", q):
            return ""
    for sec in sections:
        if sec.heading.lower() in q:
            return sec.heading
    # "this section" / "the summary" via aliases
    hint = _guess_section_hint(text, sections) if sections else ""
    if hint and re.search(
        r"\b(section|summary|only|just the|just that)\b", q
    ):
        return hint
    return ""


def _human_alignment(alignment: str) -> str:
    return _ALIGNMENT_LABELS.get(normalize_alignment(alignment), alignment.lower())


worker = CognilanceWorker(
    name="Proposal Writer Agent",
    skills=["proposal-writing"],
    description=(
        "Writes and surgically revises long-form Google Docs proposals/reports with "
        "headings, native tables, and chart images via the orchestrator Docs proxy."
    ),
    tags=["worker", "langchain", "groq", "google-docs", "proposals", "reports", "writing"],
    port=8104,
)


def _llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required")
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    return ChatGroq(
        model=model,
        api_key=api_key,
        temperature=0.4,
    )


def _structured(schema):
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    method = "json_schema" if "gpt-oss" in model.lower() else "function_calling"
    return _llm().with_structured_output(schema, method=method)


def _history_messages(history: list | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if not isinstance(history, list):
        return messages
    for item in history[-24:]:
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


def _extract_doc_id(text: str) -> str | None:
    match = _DOC_URL_RE.search(text or "")
    return match.group(1) if match else None


def _prior_from_data(prior: dict | None) -> ProposalDraft | None:
    if not isinstance(prior, dict):
        return None
    if not prior.get("title") and not prior.get("sections") and not prior.get("document_id"):
        return None
    try:
        return ProposalDraft.model_validate(
            {
                **prior,
                "title": prior.get("title") or "Untitled Document",
                "sections": prior.get("sections") or [],
            }
        )
    except Exception:
        # Minimal stub when only document_id is known.
        if prior.get("document_id"):
            return ProposalDraft(
                title=str(prior.get("title") or "Untitled Document"),
                document_id=str(prior["document_id"]),
            )
        return None


def _resolve_document_id(
    *,
    instruction: str,
    prior: ProposalDraft | None,
    history: list | None,
) -> str | None:
    if prior and prior.document_id:
        return str(prior.document_id).strip() or None
    doc_id = _extract_doc_id(instruction)
    if doc_id:
        return doc_id
    if history:
        for item in reversed(history):
            if isinstance(item, dict):
                doc_id = _extract_doc_id(str(item.get("content") or ""))
                if doc_id:
                    return doc_id
    return None


def _heading_level(named_style: str) -> int:
    if named_style == "HEADING_2":
        return 2
    if named_style == "HEADING_3":
        return 3
    return 1


def _hydrate_draft_from_live(
    *,
    existing: dict,
    prior: ProposalDraft | None,
    document_id: str,
) -> ProposalDraft:
    """Rebuild proposal IR from the live Google Doc so manual edits are respected."""
    body_content = existing.get("body_content") or []
    sections = parse_sections(body_content if isinstance(body_content, list) else [])
    title = str(existing.get("title") or "").strip()
    if not title and prior and prior.title:
        title = prior.title
    if not title:
        # Prefer TITLE paragraph text when Docs API title is empty/generic.
        for para in parse_paragraphs(body_content if isinstance(body_content, list) else []):
            if para.named_style == "TITLE":
                title = para.text.replace("\n", "").strip()
                if title:
                    break
    if not title:
        title = "Untitled Document"

    live_sections = [
        ProposalSection(
            heading=sec.heading,
            level=_heading_level(sec.named_style),  # type: ignore[arg-type]
            body=sanitize_body_text(sec.body_text),
        )
        for sec in sections
    ]
    return ProposalDraft(
        title=title,
        subtitle=(prior.subtitle if prior else "") or "",
        client=(prior.client if prior else "") or "",
        tone=(prior.tone if prior else "") or "professional",
        sections=live_sections,
        closing=(prior.closing if prior else "") or "",
        format_notes=(prior.format_notes if prior else "") or "",
        document_id=document_id,
    )


def _wants_rewrite_all(text: str) -> bool:
    q = text.lower()
    return any(
        p in q
        for p in (
            "rewrite the whole",
            "rewrite the entire",
            "rewrite everything",
            "start over",
            "replace the whole document",
            "rebuild the document",
            "rewrite the full proposal",
            "rewrite the full report",
        )
    )


def _wants_section_edit(text: str) -> bool:
    if _wants_rewrite_all(text):
        return False
    # Pure style/alignment asks are handled separately — do not rewrite section body.
    if _wants_style_edit(text) and not _has_content_edit_intent(text):
        return False
    q = text.lower()
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
    )
    return any(v in q for v in edit_verbs)


def _has_content_edit_intent(text: str) -> bool:
    """True when the user also wants wording/structure changes, not only style."""
    q = text.lower()
    content_markers = (
        "expand",
        "add more",
        "add detail",
        "more detail",
        "rewrite",
        "revise the text",
        "revise wording",
        "lengthen",
        "shorten",
        "improve the writing",
        "add content",
        "change the wording",
        "update the text",
        "edit the text",
        "edit the content",
    )
    return any(m in q for m in content_markers)


def _alignment_style_patch(text: str, sections: list) -> StylePatch | None:
    alignment = _extract_alignment(text)
    if not alignment:
        return None
    section = _style_scope_is_section(text, sections)
    if section:
        return StylePatch(alignment=alignment, scope="section", section_heading=section)
    return StylePatch(alignment=alignment, scope="document", section_heading="")


async def _apply_alignment_style(
    task_data: dict,
    *,
    document_id: str,
    style: StylePatch,
    body_content: list,
) -> dict:
    """Apply paragraph alignment or report that it is already applied."""
    paragraphs = parse_paragraphs(body_content if isinstance(body_content, list) else [])
    sections = parse_sections(body_content if isinstance(body_content, list) else [])
    target = normalize_alignment(style.alignment)
    label = _human_alignment(target)
    scope = (style.scope or "document").lower()
    section_name = (style.section_heading or "").strip()

    if scope == "section" and section_name:
        matched = find_section(sections, section_name)
        if not matched:
            names = ", ".join(s.heading for s in sections) or "(none)"
            raise OrchestratorProxyError(
                f'Could not find section "{section_name}" to align. Available: {names}'
            )
        targets = paragraphs_in_section(paragraphs, matched, include_heading=True)
        scope_label = f'section "{matched.heading}"'
        section_name = matched.heading
    else:
        targets = paragraphs
        scope_label = "the whole document"
        section_name = ""

    if not targets:
        raise OrchestratorProxyError("No paragraphs found to align in the Google Doc")

    summary = alignment_summary(targets)
    if all_aligned(targets, target):
        return {
            "document_id": document_id,
            "url": f"https://docs.google.com/document/d/{document_id}/edit",
            "status": "already_applied",
            "alignment": target,
            "scope": "section" if section_name else "document",
            "section": section_name,
            "paragraph_count": len(targets),
            "alignment_summary": summary,
            "message": (
                f"Alignment is already {_human_alignment(target)} on {scope_label} "
                f"({len(targets)} paragraph(s)). No changes were made."
            ),
        }

    requests = alignment_update_requests(targets, target)
    if not requests:
        return {
            "document_id": document_id,
            "url": f"https://docs.google.com/document/d/{document_id}/edit",
            "status": "already_applied",
            "alignment": target,
            "scope": "section" if section_name else "document",
            "section": section_name,
            "paragraph_count": len(targets),
            "alignment_summary": summary,
            "message": (
                f"Alignment is already {_human_alignment(target)} on {scope_label}. "
                "No changes were made."
            ),
        }

    result = await docs_batch_update(
        task_data,
        document_id=document_id,
        requests=requests,
    )
    url = str(
        result.get("url") or f"https://docs.google.com/document/d/{document_id}/edit"
    )
    return {
        "document_id": document_id,
        "url": url,
        "status": "applied",
        "alignment": target,
        "scope": "section" if section_name else "document",
        "section": section_name,
        "paragraph_count": len(targets),
        "request_count": len(requests),
        "alignment_summary_before": summary,
        "message": (
            f"Set {_human_alignment(target)} alignment on {scope_label} "
            f"({len(targets)} paragraph(s))."
        ),
    }


def _wants_preview(text: str) -> bool:
    q = text.lower()
    return any(
        t in q
        for t in (
            "preview",
            "export",
            "how does it look",
            "show the text",
            "plain text version",
        )
    )


def _wants_publish(text: str) -> bool:
    q = text.lower().strip().rstrip(".!")
    if q in {"create it", "write it", "publish", "create the doc", "make the doc", "go ahead"}:
        return True
    return any(
        p in text.lower()
        for p in (
            "create the google doc",
            "create google doc",
            "write the google doc",
            "put it in google docs",
            "publish to google docs",
            "create the document",
            "update the document",
            "update the google doc",
            "apply the changes",
            "write it to docs",
        )
    )


async def _compose_full(
    instruction: str,
    *,
    prior: ProposalDraft | None = None,
    history: list | None = None,
) -> ProposalDraft:
    llm = _structured(ProposalDraft)
    msgs: list[dict[str, str]] = [{"role": "system", "content": SYSTEM}]
    msgs.extend(_history_messages(history))
    if prior and (prior.sections or prior.title):
        msgs.append(
            {
                "role": "user",
                "content": (
                    "Here is the current proposal/report draft to revise or finalize "
                    f"(document_id={prior.document_id or 'none'}):\n"
                    f"{prior.model_dump_json(indent=2)}\n\n"
                    f"User request:\n{instruction}"
                ),
            }
        )
    else:
        msgs.append(
            {
                "role": "user",
                "content": (
                    "Compose a professional proposal or report based on this conversation.\n"
                    f"Latest request:\n{instruction}"
                ),
            }
        )
    draft: ProposalDraft = await llm.ainvoke(msgs)  # type: ignore[assignment]
    for section in draft.sections:
        section.body = sanitize_body_text(section.body)
    draft.closing = sanitize_body_text(draft.closing)
    return draft


async def _compose_section_patch(
    instruction: str,
    *,
    outline: str,
    target_hint: str,
    current_body: str,
    history: list | None = None,
) -> SectionPatch:
    llm = _structured(SectionPatch)
    msgs: list[dict[str, str]] = [{"role": "system", "content": SECTION_PATCH_SYSTEM}]
    msgs.extend(_history_messages(history))
    msgs.append(
        {
            "role": "user",
            "content": (
                f"Document section outline:\n{outline}\n\n"
                f"Likely target section: {target_hint or '(infer from request)'}\n"
                f"Current body of that section:\n{current_body or '(empty)'}\n\n"
                f"User edit request:\n{instruction}\n\n"
                "Return the replacement body for ONLY that section."
            ),
        }
    )
    patch: SectionPatch = await llm.ainvoke(msgs)  # type: ignore[assignment]
    patch.body = sanitize_body_text(patch.body)
    return patch


async def _end_index(task_data: dict, document_id: str) -> int:
    existing = await docs_read(task_data, document_id=document_id)
    return int(existing.get("end_index") or 1)


async def _apply_deferred(
    task_data: dict,
    *,
    document_id: str,
    deferred: list[DeferredInsert],
) -> int:
    applied = 0
    for item in deferred:
        if item.kind == "table" and item.table:
            await docs_insert_table(
                task_data,
                document_id=document_id,
                headers=list(item.table.headers or []),
                rows=[list(r) for r in (item.table.rows or [])],
            )
            applied += 1
        elif item.kind == "chart" and item.chart:
            try:
                png = chart_to_png(item.chart)
            except Exception as exc:
                raise OrchestratorProxyError(f"Chart render failed: {exc}") from exc
            await docs_insert_image(
                task_data,
                document_id=document_id,
                content_base64=base64.b64encode(png).decode("ascii"),
                mime_type="image/png",
                name=f"{(item.chart.title or 'chart').replace(' ', '_')[:40]}.png",
                width_pt=420,
            )
            applied += 1
        elif item.kind == "image" and item.image:
            img = item.image
            await docs_insert_image(
                task_data,
                document_id=document_id,
                url=(img.url or None),
                drive_file_id=(img.drive_file_id or None),
                width_pt=float(img.width_pt or 400),
                name="figure.png",
            )
            applied += 1
            caption = sanitize_body_text(img.caption or "")
            if caption:
                end = await _end_index(task_data, document_id)
                insert_at = max(1, end - 1)
                await docs_batch_update(
                    task_data,
                    document_id=document_id,
                    requests=[
                        {
                            "insertText": {
                                "location": {"index": insert_at},
                                "text": caption + "\n",
                            }
                        }
                    ],
                )
    return applied


async def _publish_full(task_data: dict, draft: ProposalDraft) -> dict:
    text_requests, deferred = draft_to_batch_requests(draft)
    document_id = (draft.document_id or "").strip()
    mode = "replace"
    url = ""

    if document_id:
        end_index = await _end_index(task_data, document_id)
        clear_reqs = clear_body_requests(end_index)
        if clear_reqs:
            await docs_batch_update(
                task_data,
                document_id=document_id,
                requests=clear_reqs,
            )
    else:
        mode = "create"
        created = await docs_create(task_data, name=draft.title.strip() or "Proposal")
        document_id = str(created.get("document_id") or "").strip()
        if not document_id:
            raise OrchestratorProxyError("Google Docs create did not return document_id")
        url = str(created.get("url") or "")
        end_index = await _end_index(task_data, document_id)
        clear_reqs = clear_body_requests(end_index)
        if clear_reqs:
            await docs_batch_update(
                task_data,
                document_id=document_id,
                requests=clear_reqs,
            )

    extras = 0
    if not deferred:
        result = await docs_batch_update(
            task_data, document_id=document_id, requests=text_requests
        )
        url = str(result.get("url") or url)
        request_count = len(text_requests)
    else:
        title_only = ProposalDraft(
            title=draft.title,
            subtitle=draft.subtitle,
            client=draft.client,
            sections=[],
            closing="",
        )
        title_reqs, _ = draft_to_batch_requests(title_only)
        request_count = len(title_reqs)
        if title_reqs:
            result = await docs_batch_update(
                task_data, document_id=document_id, requests=title_reqs
            )
            url = str(result.get("url") or url)

        for section in draft.sections:
            end = await _end_index(task_data, document_id)
            insert_at = max(1, end - 1)
            sec_reqs, _ = section_text_requests(section, index=insert_at)
            if sec_reqs:
                await docs_batch_update(
                    task_data, document_id=document_id, requests=sec_reqs
                )
                request_count += len(sec_reqs)
            extras += await _apply_deferred(
                task_data,
                document_id=document_id,
                deferred=section_deferred(section),
            )

        closing = (draft.closing or "").strip()
        if closing:
            end = await _end_index(task_data, document_id)
            close_reqs = closing_text_requests(closing, index=max(1, end - 1))
            if close_reqs:
                await docs_batch_update(
                    task_data, document_id=document_id, requests=close_reqs
                )
                request_count += len(close_reqs)
        request_count += extras

    if not url:
        url = f"https://docs.google.com/document/d/{document_id}/edit"
    return {
        "document_id": document_id,
        "url": url,
        "mode": mode,
        "request_count": request_count,
        "name": draft.title,
        "tables_charts_images": extras,
    }


async def _apply_section_patch(
    task_data: dict,
    *,
    document_id: str,
    section_heading: str,
    new_body: str,
) -> dict:
    """Delete the target section body and insert the replacement in-place."""
    existing = await docs_read(task_data, document_id=document_id)
    body_content = existing.get("body_content") or []
    sections = parse_sections(body_content if isinstance(body_content, list) else [])
    if not sections:
        raise OrchestratorProxyError(
            "Could not find headed sections in the Google Doc to edit surgically"
        )
    target = find_section(sections, section_heading)
    if not target:
        names = ", ".join(s.heading for s in sections)
        raise OrchestratorProxyError(
            f'Could not find section "{section_heading}". Available: {names}'
        )

    # Delete old body (keep heading). Docs forbids deleting the final document newline.
    doc_end = int(existing.get("end_index") or 1)
    body_start = target.body_start
    body_end = target.body_end
    if body_end >= doc_end:
        body_end = max(body_start, doc_end - 1)

    requests: list = []
    if body_end > body_start:
        requests.extend(delete_range_requests(body_start, body_end))
    insert_at = body_start
    insert_reqs = body_text_requests(new_body, index=insert_at)
    # Deletes must come before inserts in the same batch when indexes overlap;
    # after delete, insert at the same start index.
    requests.extend(insert_reqs)
    if not requests:
        raise OrchestratorProxyError("Section edit produced no Docs updates")

    result = await docs_batch_update(
        task_data,
        document_id=document_id,
        requests=requests,
    )
    url = str(
        result.get("url")
        or existing.get("url")
        or f"https://docs.google.com/document/d/{document_id}/edit"
    )
    return {
        "document_id": document_id,
        "url": url,
        "mode": "replace_section",
        "section": target.heading,
        "request_count": len(requests),
        "name": existing.get("title") or target.heading,
    }


def _output(draft: ProposalDraft, *, status: str, extra: dict | None = None) -> dict:
    data = draft.model_dump()
    data["status"] = status
    if draft.document_id and not data.get("url"):
        data["url"] = f"https://docs.google.com/document/d/{draft.document_id}/edit"
    if extra:
        data.update(extra)
    if data.get("document_id") and not data.get("url"):
        data["url"] = f"https://docs.google.com/document/d/{data['document_id']}/edit"
    return data


def _guess_section_hint(text: str, sections: list) -> str:
    q = text.lower()
    for sec in sections:
        if sec.heading.lower() in q:
            return sec.heading
    # Common aliases
    aliases = {
        "executive summary": ("executive", "summary", "exec summary"),
        "pricing": ("pricing", "investment", "budget", "cost"),
        "timeline": ("timeline", "milestone", "schedule"),
        "scope": ("scope", "scope of work"),
        "next steps": ("next steps", "closing"),
    }
    for sec in sections:
        key = sec.heading.lower()
        for alias, tokens in aliases.items():
            if alias in key or any(t in key for t in tokens):
                if any(t in q for t in tokens):
                    return sec.heading
    return sections[0].heading if sections else ""


@worker.on_task
async def handle(task):
    text = task.input.text.strip()
    data = task.input.data or {}
    prior = data.get("prior_draft")
    history = data.get("conversation_history")

    task.think("Understanding proposal/report request with conversation context")

    prior_draft = _prior_from_data(prior if isinstance(prior, dict) else None)
    document_id = _resolve_document_id(
        instruction=text, prior=prior_draft, history=history
    )
    if prior_draft and document_id and not prior_draft.document_id:
        prior_draft.document_id = document_id

    # Always read the live Doc first when we know the id — user may have edited
    # manually in the split workspace between prompts.
    live_existing: dict | None = None
    live_body_content: list | None = None
    if document_id:
        task.think("Reading live Google Doc before proceeding (picks up manual edits)")
        try:
            live_existing = await docs_read(data, document_id=document_id)
        except OrchestratorProxyError as exc:
            return task.fail(message=str(exc))
        live_body_content = live_existing.get("body_content") or []
        if not isinstance(live_body_content, list):
            live_body_content = []
        prior_draft = _hydrate_draft_from_live(
            existing=live_existing,
            prior=prior_draft,
            document_id=document_id,
        )

    if any(
        p in text.lower()
        for p in ("draft only", "don't create", "do not create", "just outline")
    ):
        task.think("Composing outline only (no Docs publish)")
        try:
            draft = await _compose_full(text, prior=prior_draft, history=history)
        except Exception as exc:
            return task.fail(message=f"Composition failed: {exc}")
        if document_id:
            draft.document_id = document_id
        outline = "\n".join(f"- {s.heading}" for s in draft.sections) or "- (no sections)"
        return task.complete(
            text=f'Draft ready — "{draft.title}"\nSections:\n{outline}',
            data=_output(draft, status="draft"),
        )

    if _wants_preview(text) and document_id:
        task.think("Exporting document preview via orchestrator proxy")
        try:
            exported = await docs_export(
                data,
                document_id=document_id,
                mime_type="text/plain",
            )
        except OrchestratorProxyError as exc:
            return task.fail(message=str(exc))
        preview = str(exported.get("text_preview") or "")[:4000]
        draft = prior_draft or ProposalDraft(title="Document", document_id=document_id)
        draft.document_id = document_id
        return task.complete(
            text=f"Preview of Google Doc ({document_id}):\n\n{preview or '(empty)'}",
            data=_output(
                draft,
                status="preview",
                extra={
                    "document_id": document_id,
                    "url": exported.get("url")
                    or (live_existing or {}).get("url")
                    or f"https://docs.google.com/document/d/{document_id}/edit",
                    "preview": preview,
                },
            ),
        )

    # Pure style/alignment: apply Docs paragraphStyle — never rewrite body text.
    if document_id and _wants_style_edit(text) and not _has_content_edit_intent(text):
        task.think("Checking and applying alignment on live Doc snapshot")
        existing = live_existing or {}
        body_content = live_body_content or []
        sections = parse_sections(body_content)
        style = _alignment_style_patch(text, sections)
        if not style:
            return task.fail(message="Could not determine the requested alignment")
        try:
            applied = await _apply_alignment_style(
                data,
                document_id=document_id,
                style=style,
                body_content=body_content,
            )
        except OrchestratorProxyError as exc:
            return task.fail(message=str(exc))
        draft = prior_draft or ProposalDraft(
            title=str(existing.get("title") or "Document"),
            document_id=document_id,
        )
        draft.document_id = document_id
        draft.format_notes = applied.get("message") or draft.format_notes
        status = "already_applied" if applied.get("status") == "already_applied" else "published"
        url = applied.get("url") or existing.get("url") or ""
        summary = str(applied.get("message") or "Alignment updated.")
        if url and status == "published":
            summary += f"\nOpen: {url}"
        return task.complete(
            text=summary,
            data=_output(draft, status=status, extra=applied),
        )

    # Surgical section edit when Doc exists and user asks to edit/expand a section.
    if document_id and _wants_section_edit(text) and not _wants_rewrite_all(text):
        task.think("Locating section to edit from live Doc snapshot")
        existing = live_existing or {}
        body_content = live_body_content or []
        sections = parse_sections(body_content)
        if sections:
            hint = _guess_section_hint(text, sections)
            matched = find_section(sections, hint) or sections[0]
            outline = sections_outline(sections)
            task.think(f'Surgically revising section "{matched.heading}"')
            try:
                patch = await _compose_section_patch(
                    text,
                    outline=outline,
                    target_hint=matched.heading,
                    current_body=matched.body_text,
                    history=history,
                )
            except Exception as exc:
                return task.fail(message=f"Section edit composition failed: {exc}")
            heading = patch.section_heading or matched.heading
            try:
                applied = await _apply_section_patch(
                    data,
                    document_id=document_id,
                    section_heading=heading,
                    new_body=patch.body,
                )
            except OrchestratorProxyError as exc:
                return task.fail(message=str(exc))

            # Mixed content + style: after body replace, apply alignment to that section.
            style_extra: dict = {}
            if _wants_style_edit(text):
                task.think("Applying alignment after section content update")
                try:
                    refreshed = await docs_read(data, document_id=document_id)
                except OrchestratorProxyError as exc:
                    return task.fail(message=str(exc))
                style = StylePatch(
                    alignment=_extract_alignment(text) or ALIGNMENT_JUSTIFIED,
                    scope="section",
                    section_heading=str(applied.get("section") or heading),
                )
                try:
                    style_extra = await _apply_alignment_style(
                        data,
                        document_id=document_id,
                        style=style,
                        body_content=refreshed.get("body_content") or [],
                    )
                except OrchestratorProxyError as exc:
                    return task.fail(message=str(exc))

            # Prefer full live IR, then overlay the section we just wrote.
            draft = prior_draft or ProposalDraft(
                title=str(existing.get("title") or "Document"),
                document_id=document_id,
            )
            draft.document_id = document_id
            draft.format_notes = (patch.format_notes or "").strip() or draft.format_notes
            applied_heading = str(applied.get("section") or heading)
            clean_body = sanitize_body_text(patch.body)
            updated = False
            for sec in draft.sections:
                h = sec.heading.lower()
                target = applied_heading.lower()
                if h == target or target in h or h in target:
                    sec.body = clean_body
                    updated = True
                    break
            if not updated:
                draft.sections.append(
                    ProposalSection(heading=applied_heading, body=clean_body)
                )

            url = applied.get("url") or ""
            notes = (patch.format_notes or "").strip()
            summary = (
                f'Updated section "{applied_heading}" '
                f'in Google Doc "{draft.title}".'
            )
            if style_extra.get("message"):
                summary += f"\n{style_extra['message']}"
            if url:
                summary += f"\nOpen: {url}"
            if notes:
                summary += f"\nFormatting: {notes}"
            extra = {**applied}
            if style_extra:
                extra["alignment_result"] = style_extra
            return task.complete(
                text=summary,
                data=_output(draft, status="published", extra=extra),
            )
        task.think("No headed sections found — falling back to full document rewrite")

    # Full create / rewrite_all (compose from live-hydrated prior when Doc exists)
    task.think("Composing full document structure with Groq")
    try:
        draft = await _compose_full(text, prior=prior_draft, history=history)
    except Exception as exc:
        return task.fail(message=f"Composition failed: {exc}")
    if document_id:
        draft.document_id = document_id

    publish = (
        _wants_publish(text)
        or _wants_rewrite_all(text)
        or not prior_draft
        or bool(
            re.search(
                r"\b(proposal|rfp|sow|statement of work|report|business report)\b",
                text,
                re.I,
            )
        )
        or bool(document_id and _wants_section_edit(text))
    )

    if publish:
        task.think("Writing formatted document into Google Docs via proxy")
        try:
            published = await _publish_full(data, draft)
        except OrchestratorProxyError as exc:
            return task.fail(message=str(exc))
        draft.document_id = str(published.get("document_id") or draft.document_id)
        url = published.get("url") or ""
        notes = (draft.format_notes or "").strip()
        summary = f'Created Google Doc "{draft.title}".'
        if published.get("mode") == "replace":
            summary = f'Updated Google Doc "{draft.title}".'
        if url:
            summary += f"\nOpen: {url}"
        if notes:
            summary += f"\nFormatting: {notes}"
        return task.complete(
            text=summary,
            data=_output(draft, status="published", extra=published),
        )

    outline = "\n".join(f"- {s.heading}" for s in draft.sections) or "- (no sections)"
    return task.complete(
        text=f'Draft ready — "{draft.title}"\nSections:\n{outline}',
        data=_output(draft, status="draft"),
    )


if __name__ == "__main__":
    worker.run()
