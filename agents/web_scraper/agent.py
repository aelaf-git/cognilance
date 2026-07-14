"""Web Scraper Agent — Groq + LangChain + CognilanceWorker."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cognilance import CognilanceWorker
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from scrape import extract_urls, fetch_pages, web_search

_AGENT_DIR = Path(__file__).resolve().parent
load_dotenv(_AGENT_DIR / ".env")

MAX_PAGES = 4
MAX_SEARCH_RESULTS = 6

SYSTEM = """You are a precise web data extraction specialist.
You receive scraped page content (already fetched) and the user's request.

RULES
- Answer ONLY from the provided page content. Never fabricate facts, numbers, or quotes.
- Cite which source URL each key fact came from.
- If pages did not contain the answer, say so plainly in `summary` and set what you could
  not find — do not guess.
- Prefer structured extraction: when the user asks for tables, lists, prices, dates,
  specs, or comparisons, put machine-usable values in `extracted` (JSON-friendly).
- Keep `summary` focused on the user's actual question, not generic page descriptions.
- Honor conversation context (e.g. "scrape that link", "compare these two sites")."""


class SourceRef(BaseModel):
    title: str = Field(description="Page or result title")
    url: str = Field(description="Source URL")
    snippet: str = Field(default="", description="Short relevant excerpt from this source")


class ScrapeResult(BaseModel):
    summary: str = Field(description="Synthesized answer to the user's request, grounded in sources")
    sources: list[SourceRef] = Field(default_factory=list, description="Sources actually used")
    extracted: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured data extracted (fields, lists, tables) when applicable",
    )
    status: str = Field(
        default="ok",
        description="ok = answered fully; partial = some info missing; failed = nothing usable",
    )


worker = CognilanceWorker(
    name="Web Scraper Agent",
    skills=["web-scraping"],
    description=(
        "Searches the web, scrapes pages, and extracts structured data and grounded "
        "answers with sources."
    ),
    tags=["worker", "langchain", "groq", "web", "scraping", "research"],
    port=8102,
)


def _llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    return ChatGroq(
        model=model,
        api_key=api_key,
        temperature=0.2,
    ).with_structured_output(ScrapeResult)


def _history_messages(history: list | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if not isinstance(history, list):
        return messages
    for item in history[-16:]:
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


def _pages_context(pages: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for i, page in enumerate(pages, start=1):
        if page.get("error"):
            blocks.append(f"[Source {i}] {page['url']}\nFETCH ERROR: {page['error']}")
            continue
        blocks.append(
            f"[Source {i}] {page.get('title') or page['url']}\nURL: {page['url']}\n\n"
            f"{page.get('content') or '(empty page)'}"
        )
    return "\n\n---\n\n".join(blocks)


async def _extract(
    instruction: str,
    pages: list[dict[str, Any]],
    *,
    history: list | None = None,
) -> ScrapeResult:
    llm = _llm()
    msgs: list[dict[str, str]] = [{"role": "system", "content": SYSTEM}]
    msgs.extend(_history_messages(history))
    msgs.append(
        {
            "role": "user",
            "content": (
                f"User request:\n{instruction}\n\n"
                f"Scraped content from {len(pages)} page(s):\n\n{_pages_context(pages)}"
            ),
        }
    )
    return await llm.ainvoke(msgs)  # type: ignore[return-value]


def _output(result: ScrapeResult, *, pages: list[dict[str, Any]]) -> dict[str, Any]:
    sources = [s.model_dump() for s in result.sources]
    if not sources:
        sources = [
            {"title": p.get("title") or p["url"], "url": p["url"], "snippet": ""}
            for p in pages
            if not p.get("error")
        ]
    return {
        "summary": result.summary,
        "sources": sources,
        "extracted": result.extracted,
        "status": result.status,
        "pages_fetched": len([p for p in pages if not p.get("error")]),
    }


@worker.on_task
async def handle(task):
    text = task.input.text.strip()
    data = task.input.data or {}
    history = data.get("conversation_history")

    task.think("Reading scrape request")

    urls = extract_urls(text)
    if not urls and isinstance(history, list):
        # Fall back to URLs mentioned earlier in the conversation ("scrape that link").
        for item in reversed(history):
            if isinstance(item, dict):
                urls = extract_urls(str(item.get("content") or ""))
                if urls:
                    break

    search_results: list[dict[str, Any]] = []
    if urls:
        task.think(f"Fetching {min(len(urls), MAX_PAGES)} page(s)")
    else:
        task.think("No URL given — searching the web first")
        try:
            search_results = await web_search(text, max_results=MAX_SEARCH_RESULTS)
        except Exception as exc:
            return task.fail(message=f"Web search failed: {exc}")
        if not search_results:
            return task.complete(
                text="No web results found for this request.",
                data={"summary": "No web results found.", "sources": [], "status": "failed"},
            )
        urls = [r["url"] for r in search_results]
        task.think(f"Found {len(search_results)} results — scraping top {MAX_PAGES}")

    pages = await fetch_pages(urls, max_pages=MAX_PAGES)
    fetched = [p for p in pages if not p.get("error")]
    if not fetched:
        errors = "; ".join(str(p.get("error")) for p in pages)
        return task.fail(message=f"Could not fetch any pages: {errors}")

    task.think(f"Extracting data from {len(fetched)} page(s) with Groq")
    try:
        result = await _extract(text, pages, history=history)
    except Exception as exc:
        return task.fail(message=f"Extraction failed: {exc}")

    # Merge search snippets into sources missing them.
    snippet_by_url = {r["url"]: r.get("snippet", "") for r in search_results}
    for source in result.sources:
        if not source.snippet and source.url in snippet_by_url:
            source.snippet = snippet_by_url[source.url]

    return task.complete(
        text=result.summary,
        data=_output(result, pages=pages),
    )


if __name__ == "__main__":
    worker.run()
