"""Heuristic routing for web search, fetch, scrape, and link validation."""

from __future__ import annotations

import re

from cognilance.core.models import AgentCard

from orchestrator.registry_cache import has_agent_for_skill
from orchestrator.state import Subtask
from orchestrator.tools.web import extract_urls


def _mentions(query: str, *terms: str) -> bool:
    q = query.lower()
    return any(term in q for term in terms)


def _is_app_specific_task(query: str) -> bool:
    q = query.lower()
    app_terms = (
        "gmail",
        "inbox",
        "my email",
        "my emails",
        "google calendar",
        "my calendar",
        "google drive",
        "my drive",
        "notion",
        "slack",
        "github repo",
        "my github",
    )
    return any(term in q for term in app_terms)


def _wants_web_fetch(query: str) -> bool:
    urls = extract_urls(query)
    if not urls:
        return False
    q = query.lower()
    if _mentions(
        q,
        "fetch",
        "scrape",
        "read this",
        "read the page",
        "summarize this",
        "summarize the page",
        "open this",
        "get content",
        "what does this page",
        "what's on this",
        "whats on this",
        "from this url",
        "from this link",
    ):
        return True
    stripped = re.sub(r"https?://\S+", "", q).strip()
    return len(stripped) < 40 and len(urls) == 1


def _wants_web_search(query: str) -> bool:
    if _is_app_specific_task(query):
        return False
    q = query.lower()
    if _mentions(
        q,
        "search the web",
        "web search",
        "look up online",
        "look this up",
        "google it",
        "on the internet",
        "on the web",
        "latest news",
        "current news",
        "recent news",
        "find online",
        "search online",
        "research",
    ):
        return True
    if _mentions(q, "who is ", "what is ", "when did ", "where is "):
        return True
    if "search for" in q or "search about" in q:
        return True
    if q.startswith("search ") and not _is_app_specific_task(query):
        return True
    return False


def _search_query_from_instruction(query: str) -> str:
    q = query.strip()
    for prefix in (
        "search the web for ",
        "search the web about ",
        "web search for ",
        "look up ",
        "look up online ",
        "search for ",
        "search about ",
        "find online ",
        "google ",
        "research ",
    ):
        if q.lower().startswith(prefix):
            return q[len(prefix) :].strip(" ?.")
    return q


def _wants_link_validation(query: str) -> bool:
    q = query.lower()
    if not extract_urls(query) and "link" not in q and "url" not in q:
        return False
    return any(
        term in q
        for term in (
            "check the link",
            "check this link",
            "check these link",
            "check those link",
            "check if the link",
            "check if this link",
            "validate",
            "verify",
            "broken link",
            "dead link",
            "links work",
            "link works",
            "is working",
            "are working",
            "still work",
            "functional",
            "reachable",
        )
    )


def web_subtasks_for_query(
    query: str,
    *,
    catalog_agents: list[AgentCard] | None = None,
) -> list[Subtask] | None:
    """Return hire/web subtasks when the user needs search, fetch, or link checks.

    Policy: matching catalog skill → hire; else built-in web tools.
    """
    agents = catalog_agents or []

    if _wants_link_validation(query):
        if has_agent_for_skill(agents, "link-validation"):
            return [
                {
                    "id": "link-validator",
                    "title": "Validate links",
                    "instruction": query,
                    "tool": "hire:link-validation",
                    "skill": "link-validation",
                    "assignee": "link-validation",
                    "depends_on": [],
                }
            ]

    if _wants_web_fetch(query) or _wants_web_search(query):
        if has_agent_for_skill(agents, "web-scraping"):
            return [
                {
                    "id": "web-scraper",
                    "title": "Web research / scrape",
                    "instruction": query,
                    "tool": "hire:web-scraping",
                    "skill": "web-scraping",
                    "assignee": "web-scraping",
                    "depends_on": [],
                }
            ]

    if _wants_web_fetch(query):
        url = extract_urls(query)[0]
        return [
            {
                "id": "web-fetch",
                "title": "Fetch web page",
                "instruction": query,
                "tool": "web",
                "action": "fetch_url",
                "params": {"url": url},
                "assignee": "web",
                "depends_on": [],
            }
        ]

    if _wants_web_search(query):
        search_q = _search_query_from_instruction(query)
        return [
            {
                "id": "web-search",
                "title": "Search the web",
                "instruction": query,
                "tool": "web",
                "action": "search",
                "params": {"query": search_q, "max_results": 6},
                "assignee": "web",
                "depends_on": [],
            }
        ]

    return None
