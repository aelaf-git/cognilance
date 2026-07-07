"""Built-in web search and page fetching for the orchestrator."""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse

import httpx

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; CognilanceOrchestrator/1.0; +https://cognilance.local)"
)
MAX_FETCH_BYTES = 2_000_000
MAX_CONTENT_CHARS = 12_000


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"} and not self._skip_depth:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._chunks.append(text + " ")

    def text(self) -> str:
        raw = "".join(self._chunks)
        return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", raw)).strip()


def extract_urls(text: str) -> list[str]:
    pattern = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
    urls: list[str] = []
    for match in pattern.finditer(text):
        url = match.group(0).rstrip(".,;)")
        if url not in urls:
            urls.append(url)
    return urls


def _normalize_results(items: list[dict[str, Any]], *, query: str) -> dict[str, Any]:
    sources = [
        {
            "title": item.get("title") or item.get("url") or "Result",
            "url": item.get("url") or "",
            "snippet": item.get("snippet") or "",
        }
        for item in items
        if item.get("url")
    ]
    return {
        "query": query,
        "results": items,
        "sources": sources,
        "count": len(items),
    }


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
            raise RuntimeError(f"Tavily search failed: {response.text[:500]}")
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
            raise RuntimeError(f"Serper search failed: {response.text[:500]}")
        data = response.json()
    organic = data.get("organic") or []
    return [
        {
            "title": item.get("title") or "",
            "url": item.get("link") or "",
            "snippet": item.get("snippet") or "",
        }
        for item in organic[:max_results]
    ]


async def _search_brave(query: str, *, max_results: int) -> list[dict[str, Any]]:
    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        return []
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": query, "count": max_results},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Brave search failed: {response.text[:500]}")
        data = response.json()
    web = data.get("web") or {}
    return [
        {
            "title": item.get("title") or "",
            "url": item.get("url") or "",
            "snippet": item.get("description") or "",
        }
        for item in web.get("results", [])[:max_results]
    ]


async def _search_duckduckgo(query: str, *, max_results: int) -> list[dict[str, Any]]:
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": "", "kl": "wt-wt"},
            headers=headers,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"DuckDuckGo search failed: HTTP {response.status_code}")
        html = response.text

    results: list[dict[str, Any]] = []
    for block in re.findall(
        r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        url = unquote(block[0].replace("&amp;", "&"))
        if "uddg=" in url:
            match = re.search(r"uddg=([^&]+)", url)
            if match:
                url = unquote(match.group(1))
        title = re.sub(r"<[^>]+>", "", block[1]).strip()
        snippet = re.sub(r"<[^>]+>", "", block[2]).strip()
        if url.startswith("http"):
            results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break

    if not results:
        for match in re.finditer(
            r'class="result__title"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            url = unquote(match.group(1).replace("&amp;", "&"))
            if "uddg=" in url:
                uddg = re.search(r"uddg=([^&]+)", url)
                if uddg:
                    url = unquote(uddg.group(1))
            title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            if url.startswith("http"):
                results.append({"title": title, "url": url, "snippet": ""})
            if len(results) >= max_results:
                break

    return results


async def web_search(
    query: str,
    *,
    max_results: int = 5,
) -> dict[str, Any]:
    q = query.strip()
    if not q:
        raise RuntimeError("query is required for web search")

    provider = os.getenv("WEB_SEARCH_PROVIDER", "").strip().lower()
    items: list[dict[str, Any]] = []
    errors: list[str] = []

    providers: list[str]
    if provider in {"tavily", "serper", "brave", "duckduckgo"}:
        providers = [provider, "duckduckgo"]
    else:
        providers = ["tavily", "serper", "brave", "duckduckgo"]

    for name in providers:
        try:
            if name == "tavily":
                items = await _search_tavily(q, max_results=max_results)
            elif name == "serper":
                items = await _search_serper(q, max_results=max_results)
            elif name == "brave":
                items = await _search_brave(q, max_results=max_results)
            else:
                items = await _search_duckduckgo(q, max_results=max_results)
            if items:
                return _normalize_results(items, query=q)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            continue

    if errors:
        raise RuntimeError("; ".join(errors))
    return _normalize_results([], query=q)


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))).strip()


def _validate_fetch_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError("Only http and https URLs are supported")
    if not parsed.netloc:
        raise RuntimeError("Invalid URL")
    return url.strip()


async def web_fetch(
    url: str,
    *,
    max_chars: int = MAX_CONTENT_CHARS,
) -> dict[str, Any]:
    target = _validate_fetch_url(url)
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(target, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"Failed to fetch URL: HTTP {response.status_code}")

        content_type = response.headers.get("content-type", "").lower()
        raw = response.content[:MAX_FETCH_BYTES]

        if "application/json" in content_type:
            text = raw.decode("utf-8", errors="replace")
            return {
                "url": str(response.url),
                "title": target,
                "content_type": content_type,
                "content": text[:max_chars],
                "truncated": len(text) > max_chars,
            }

        if "text/html" in content_type or raw.lstrip()[:1] in {b"<", b"\xef"}:
            html = raw.decode("utf-8", errors="replace")
            parser = _TextExtractor()
            parser.feed(html)
            text = parser.text()
            title = _extract_title(html) or target
            return {
                "url": str(response.url),
                "title": title,
                "content_type": content_type or "text/html",
                "content": text[:max_chars],
                "truncated": len(text) > max_chars,
            }

        text = raw.decode("utf-8", errors="replace")
        return {
            "url": str(response.url),
            "title": target,
            "content_type": content_type or "text/plain",
            "content": text[:max_chars],
            "truncated": len(text) > max_chars,
        }


def format_web_search_result(result: dict[str, Any]) -> str:
    results = result.get("results") or []
    query = result.get("query") or ""
    if not results:
        return f'No web results found for "{query}".'

    lines = [f'Web search for "{query}" — {len(results)} result(s):\n']
    for i, item in enumerate(results, 1):
        title = item.get("title") or "(no title)"
        url = item.get("url") or ""
        snippet = item.get("snippet") or ""
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   {url}")
        if snippet:
            lines.append(f"   {snippet[:300]}")
        lines.append("")
    return "\n".join(lines).strip()


def format_web_fetch_result(result: dict[str, Any]) -> str:
    title = result.get("title") or result.get("url") or "Page"
    url = result.get("url") or ""
    content = (result.get("content") or "").strip()
    lines = [f'Fetched: "{title}"', f"URL: {url}"]
    if result.get("truncated"):
        lines.append("(Content truncated for length.)")
    if content:
        preview = content[:2500]
        lines.append(f"\nContent:\n{preview}")
    else:
        lines.append("\n(No readable text extracted.)")
    return "\n".join(lines)


def search_provider_status() -> str:
    if os.getenv("TAVILY_API_KEY"):
        return "tavily (API key set)"
    if os.getenv("SERPER_API_KEY"):
        return "serper (API key set)"
    if os.getenv("BRAVE_SEARCH_API_KEY"):
        return "brave (API key set)"
    return "duckduckgo (no API key required)"
