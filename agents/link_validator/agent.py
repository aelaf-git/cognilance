"""Link Validator Agent — checks URLs are functional; Groq writes the report."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from validate import check_links, extract_links, summarize

_AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(_AGENT_DIR / ".env")

ANALYSIS_SYSTEM = """You are a link-validation analyst. You receive HTTP check results
for a set of URLs (verdict ok / warning / broken, status codes, notes).

Produce:
- report: a short, friendly Markdown report of the findings. Lead with the overall
  outcome, then list broken links (with why they failed) and warnings. Never invent
  results — use only the provided check data.
- correction_request: ONLY when there are broken links — a clear, actionable
  instruction for the agent that produced these links, telling it exactly which URLs
  are broken (list them verbatim), why they failed, and asking it to replace them with
  working alternatives and re-deliver its output. Empty string when nothing is broken."""


class LinkAnalysis(BaseModel):
    report: str = Field(description="Markdown report of the validation findings")
    correction_request: str = Field(
        default="",
        description="Instruction for the responsible agent to fix broken links; empty if none",
    )


def _llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    return ChatGroq(model=model, api_key=api_key, temperature=0.2).with_structured_output(
        LinkAnalysis
    )


def _fallback_correction(results: list[dict[str, Any]]) -> str:
    broken = [r for r in results if r["verdict"] == "broken"]
    if not broken:
        return ""
    lines = [
        "The following links in your output are broken — replace them with working "
        "alternatives and re-deliver your result:",
    ]
    lines.extend(f"- {r['url']} ({r['note']})" for r in broken)
    return "\n".join(lines)


async def _analyze(results: list[dict[str, Any]], request: str) -> LinkAnalysis:
    """Groq writes the report; deterministic fallback keeps the agent key-optional."""
    checks = "\n".join(
        f"- {r['url']} → verdict={r['verdict']}, status={r['status_code']}, "
        f"note={r['note']}, final_url={r.get('final_url', r['url'])}"
        for r in results
    )
    try:
        llm = _llm()
        return await llm.ainvoke(
            [
                {"role": "system", "content": ANALYSIS_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{request}\n\nLink check results:\n{checks}"
                    ),
                },
            ]
        )  # type: ignore[return-value]
    except Exception:
        return LinkAnalysis(
            report=summarize(results),
            correction_request=_fallback_correction(results),
        )

worker = CognilanceWorker(
    name="Link Validator Agent",
    skills=["link-validation"],
    description=(
        "Validates URLs: checks that links are reachable, follows redirects, and "
        "reports broken or suspicious links with HTTP status details."
    ),
    tags=["worker", "links", "validation", "qa", "web"],
    port=8103,
)


def _links_from_history(history: Any) -> list[str]:
    """Fall back to links mentioned earlier in the conversation ('check those links')."""
    if not isinstance(history, list):
        return []
    for item in reversed(history):
        if isinstance(item, dict):
            links = extract_links(str(item.get("content") or ""))
            if links:
                return links
    return []


def _links_from_data(data: dict[str, Any]) -> list[str]:
    """Links passed structurally by the orchestrator or another agent's output."""
    links: list[str] = []
    raw = data.get("urls") or data.get("links")
    if isinstance(raw, list):
        links.extend(str(u) for u in raw if u)
    for source in data.get("sources") or []:
        if isinstance(source, dict) and source.get("url"):
            links.append(str(source["url"]))
    if data.get("body"):
        links.extend(extract_links(str(data["body"])))
    seen: set[str] = set()
    unique = []
    for url in links:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


@worker.on_task
async def handle(task):
    text = task.input.text.strip()
    data = task.input.data or {}

    task.think("Collecting links to validate")
    links = extract_links(text)
    if not links:
        links = _links_from_data(data)
    if not links:
        links = _links_from_history(data.get("conversation_history"))

    if not links:
        return task.complete(
            text="No links found to validate — share the URLs you want checked.",
            data={"summary": "No links found.", "results": [], "status": "no_links"},
        )

    task.think(f"Checking {len(links)} link(s) concurrently")
    results = await check_links(links)

    broken = sum(1 for r in results if r["verdict"] == "broken")
    warnings = sum(1 for r in results if r["verdict"] == "warning")
    status = "ok" if broken == 0 else "issues_found"

    task.think("Analyzing results with Groq")
    analysis = await _analyze(results, text)
    summary = analysis.report or summarize(results)
    correction_request = analysis.correction_request.strip() if broken else ""
    if broken and not correction_request:
        correction_request = _fallback_correction(results)

    # sources shape lets the research-sources UI card render the per-link report.
    sources = [
        {
            "title": f"[{r['verdict'].upper()}] {r['note']}"
            + (f" · {r['elapsed_ms']}ms" if r.get("elapsed_ms") else ""),
            "url": r["url"],
            "snippet": (
                f"Final URL: {r['final_url']}" if r.get("final_url") and r["final_url"] != r["url"] else ""
            ),
        }
        for r in results
    ]

    return task.complete(
        text=summary,
        data={
            "summary": summary,
            "results": results,
            "sources": sources,
            "checked": len(results),
            "ok": len(results) - broken - warnings,
            "warnings": warnings,
            "broken": broken,
            "broken_links": [r["url"] for r in results if r["verdict"] == "broken"],
            "correction_request": correction_request,
            "status": status,
        },
    )


if __name__ == "__main__":
    worker.run()
