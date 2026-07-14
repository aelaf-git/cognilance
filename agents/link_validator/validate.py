"""Concurrent link checking for the Link Validator Agent."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
CHECK_TIMEOUT = 15.0
MAX_LINKS = 25
MAX_CONCURRENCY = 8

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_HREF_RE = re.compile(r"""href\s*=\s*['"](https?://[^'"]+)['"]""", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")


def extract_links(text: str) -> list[str]:
    """Pull URLs out of plain text, markdown links, and HTML hrefs."""
    urls: list[str] = []
    for pattern in (_HREF_RE, _MARKDOWN_LINK_RE, _URL_RE):
        for match in pattern.finditer(text or ""):
            url = match.group(1) if pattern is not _URL_RE else match.group(0)
            url = url.rstrip(".,;)'\"")
            if url not in urls:
                urls.append(url)
    return urls


def _classify(status_code: int, redirected: bool) -> tuple[str, str]:
    """Return (verdict, note) — verdict is ok / warning / broken."""
    if 200 <= status_code < 300:
        if redirected:
            return "ok", "Reachable (followed redirect)"
        return "ok", "Reachable"
    if status_code in (401, 403):
        return "warning", f"HTTP {status_code} — exists but requires authorization"
    if status_code == 429:
        return "warning", "HTTP 429 — rate limited, likely valid"
    if status_code == 405:
        return "warning", "HTTP 405 — method not allowed (page may still work)"
    if 300 <= status_code < 400:
        return "warning", f"HTTP {status_code} — unresolved redirect"
    return "broken", f"HTTP {status_code}"


async def check_link(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    """Check one URL: HEAD first, GET fallback (some servers reject HEAD)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {
            "url": url,
            "verdict": "broken",
            "status_code": None,
            "final_url": url,
            "note": "Malformed URL",
            "elapsed_ms": 0,
        }

    started = time.monotonic()
    response: httpx.Response | None = None
    error: str | None = None
    for method in ("HEAD", "GET"):
        try:
            response = await client.request(method, url)
            error = None
            # Servers that dislike HEAD often answer 4xx/5xx to it but 200 to GET.
            if method == "HEAD" and response.status_code >= 400:
                continue
            break
        except httpx.TimeoutException:
            error = f"Timed out after {CHECK_TIMEOUT:.0f}s"
        except httpx.HTTPError as exc:
            error = str(exc) or exc.__class__.__name__

    elapsed_ms = int((time.monotonic() - started) * 1000)

    if response is None:
        return {
            "url": url,
            "verdict": "broken",
            "status_code": None,
            "final_url": url,
            "note": error or "Connection failed",
            "elapsed_ms": elapsed_ms,
        }

    redirected = str(response.url) != url
    verdict, note = _classify(response.status_code, redirected)
    return {
        "url": url,
        "verdict": verdict,
        "status_code": response.status_code,
        "final_url": str(response.url),
        "content_type": response.headers.get("content-type", "").split(";")[0],
        "note": note,
        "elapsed_ms": elapsed_ms,
    }


async def check_links(urls: list[str]) -> list[dict[str, Any]]:
    """Validate up to MAX_LINKS URLs concurrently, preserving input order."""
    targets = urls[:MAX_LINKS]
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async with httpx.AsyncClient(
        timeout=CHECK_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    ) as client:

        async def bounded(url: str) -> dict[str, Any]:
            async with semaphore:
                return await check_link(client, url)

        return list(await asyncio.gather(*(bounded(u) for u in targets)))


def summarize(results: list[dict[str, Any]]) -> str:
    """Markdown summary of validation results."""
    ok = [r for r in results if r["verdict"] == "ok"]
    warn = [r for r in results if r["verdict"] == "warning"]
    broken = [r for r in results if r["verdict"] == "broken"]

    if not results:
        return "No links found to validate."

    if not broken and not warn:
        head = f"All {len(results)} link(s) are working."
    elif broken:
        head = (
            f"Checked {len(results)} link(s): {len(ok)} working, "
            f"{len(warn)} with warnings, {len(broken)} broken."
        )
    else:
        head = f"Checked {len(results)} link(s): {len(ok)} working, {len(warn)} with warnings."

    lines = [head]
    if broken:
        lines.append("")
        lines.append("**Broken:**")
        lines.extend(f"- {r['url']} — {r['note']}" for r in broken)
    if warn:
        lines.append("")
        lines.append("**Warnings:**")
        lines.extend(f"- {r['url']} — {r['note']}" for r in warn)
    return "\n".join(lines)
