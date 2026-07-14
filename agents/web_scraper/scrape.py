"""Web search, page fetching, and HTML cleaning for the Web Scraper Agent."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
MAX_FETCH_BYTES = 2_500_000
MAX_PAGE_CHARS = 9_000
FETCH_TIMEOUT = 25.0

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)

_STRIP_TAGS = ("script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form")

_BLOCK_TAGS = [
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "tr", "pre", "blockquote", "dt", "dd", "figcaption",
]


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in _URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;)")
        if url not in urls:
            urls.append(url)
    return urls


def _validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError("Only http and https URLs are supported")
    if not parsed.netloc:
        raise RuntimeError(f"Invalid URL: {url}")
    return url.strip()


def clean_html(html: str) -> tuple[str, str]:
    """Return (title, readable text) from raw HTML."""
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "") or ""

    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    # Prefer main content containers when present.
    main = soup.find("article") or soup.find("main") or soup.body or soup

    # One line per block element keeps inline markup ("Hello <b>world</b>") intact.
    lines: list[str] = []
    for block in main.find_all(_BLOCK_TAGS):
        if block.find_parent(_BLOCK_TAGS) is not None:
            continue  # e.g. <p> inside <li> — the outer block already covers it
        line = block.get_text(" ", strip=True)
        if line:
            lines.append(line)
    text = "\n".join(lines)

    # Pages built from bare <div>s have no block tags — fall back to full text.
    if len(text) < 200:
        fallback = main.get_text(" ", strip=True)
        if len(fallback) > len(text):
            text = fallback

    text = re.sub(r"[ \t]+", " ", text)
    return title, text.strip()


async def fetch_page(url: str, *, max_chars: int = MAX_PAGE_CHARS) -> dict[str, Any]:
    """Fetch one URL and return {url, title, content, truncated}."""
    target = _validate_url(url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(target, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} fetching {target}")
        content_type = response.headers.get("content-type", "").lower()
        raw = response.content[:MAX_FETCH_BYTES]

    if "application/json" in content_type:
        text = raw.decode("utf-8", errors="replace")
        return {
            "url": str(response.url),
            "title": target,
            "content": text[:max_chars],
            "truncated": len(text) > max_chars,
        }

    if "text/html" in content_type or raw.lstrip()[:1] in {b"<", b"\xef"}:
        html = raw.decode("utf-8", errors="replace")
        title, text = clean_html(html)
        return {
            "url": str(response.url),
            "title": title or target,
            "content": text[:max_chars],
            "truncated": len(text) > max_chars,
        }

    text = raw.decode("utf-8", errors="replace")
    return {
        "url": str(response.url),
        "title": target,
        "content": text[:max_chars],
        "truncated": len(text) > max_chars,
    }


async def fetch_pages(urls: list[str], *, max_pages: int = 4) -> list[dict[str, Any]]:
    """Fetch several URLs concurrently; failures become error entries."""
    targets = urls[:max_pages]
    results = await asyncio.gather(
        *(fetch_page(u) for u in targets), return_exceptions=True
    )
    pages: list[dict[str, Any]] = []
    for url, result in zip(targets, results):
        if isinstance(result, Exception):
            pages.append({"url": url, "title": url, "content": "", "error": str(result)})
        else:
            pages.append(result)
    return pages


async def _search_tavily(query: str, *, max_results: int) -> list[dict[str, Any]]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": False,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Tavily search failed: {response.text[:300]}")
        data = response.json()
    return [
        {
            "title": item.get("title") or "",
            "url": item.get("url") or "",
            "snippet": item.get("content") or "",
        }
        for item in data.get("results", [])[:max_results]
    ]


async def _search_serper(query: str, *, max_results: int) -> list[dict[str, Any]]:
    api_key = os.getenv("SERPER_API_KEY", "").strip()
    if not api_key:
        return []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Serper search failed: {response.text[:300]}")
        data = response.json()
    return [
        {
            "title": item.get("title") or "",
            "url": item.get("link") or "",
            "snippet": item.get("snippet") or "",
        }
        for item in (data.get("organic") or [])[:max_results]
    ]


async def _search_duckduckgo(query: str, *, max_results: int) -> list[dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": "", "kl": "wt-wt"},
            headers=headers,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"DuckDuckGo search failed: HTTP {response.status_code}")
        html = response.text

    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, Any]] = []
    for block in soup.select(".result"):
        link = block.select_one("a.result__a")
        if not link or not link.get("href"):
            continue
        url = unquote(str(link["href"]).replace("&amp;", "&"))
        if "uddg=" in url:
            match = re.search(r"uddg=([^&]+)", url)
            if match:
                url = unquote(match.group(1))
        if not url.startswith("http"):
            continue
        snippet_el = block.select_one(".result__snippet")
        results.append(
            {
                "title": link.get_text(strip=True),
                "url": url,
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            }
        )
        if len(results) >= max_results:
            break
    return results


async def web_search(query: str, *, max_results: int = 6) -> list[dict[str, Any]]:
    """Search with the best available provider; DuckDuckGo needs no API key."""
    q = query.strip()
    if not q:
        raise RuntimeError("query is required for web search")

    errors: list[str] = []
    for provider in (_search_tavily, _search_serper, _search_duckduckgo):
        try:
            items = await provider(q, max_results=max_results)
            if items:
                return items
        except Exception as exc:
            errors.append(str(exc))
    if errors:
        raise RuntimeError("; ".join(errors))
    return []
