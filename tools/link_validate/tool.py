"""In-process link validation for the researcher role."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

import httpx

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
USER_AGENT = "CognilanceResearcher/1.0"
CHECK_TIMEOUT = 12.0
MAX_LINKS = 20


def extract_links(text: str) -> list[str]:
    urls: list[str] = []
    for match in _URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;)'\"")
        if url not in urls:
            urls.append(url)
    return urls[:MAX_LINKS]


async def _check_one(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"url": url, "verdict": "broken", "note": "Invalid URL"}
    try:
        resp = await client.head(url, follow_redirects=True)
        if resp.status_code == 405:
            resp = await client.get(url, follow_redirects=True)
        code = resp.status_code
        if 200 <= code < 300:
            return {"url": url, "verdict": "ok", "status_code": code, "note": "Reachable"}
        if code in {401, 403, 429}:
            return {"url": url, "verdict": "warning", "status_code": code, "note": f"HTTP {code}"}
        return {"url": url, "verdict": "broken", "status_code": code, "note": f"HTTP {code}"}
    except Exception as exc:
        return {"url": url, "verdict": "broken", "note": str(exc)[:200]}


async def validate_links(text_or_urls: str | list[str]) -> dict[str, Any]:
    if isinstance(text_or_urls, list):
        urls = text_or_urls[:MAX_LINKS]
    else:
        urls = extract_links(text_or_urls)
    if not urls:
        return {"links": [], "ok": 0, "broken": 0, "warning": 0, "summary": "No links found."}
    async with httpx.AsyncClient(
        timeout=CHECK_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        results = await asyncio.gather(*[_check_one(client, u) for u in urls])
    counts = {"ok": 0, "broken": 0, "warning": 0}
    for row in results:
        counts[row.get("verdict", "broken")] = counts.get(row.get("verdict", "broken"), 0) + 1
    summary = (
        f"Checked {len(results)} links: "
        f"{counts['ok']} ok, {counts['warning']} warning, {counts['broken']} broken."
    )
    return {"links": list(results), **counts, "summary": summary}


async def run(action: str, *, instruction: str, params: dict[str, Any], ctx: Any) -> Any:
    """Registry entrypoint (see tools/registry.py)."""
    from tools.registry import ToolOutput

    if action != "check":
        raise RuntimeError(f"Unknown link_validate action: {action}")
    result = await validate_links(str(params.get("text") or instruction))
    return ToolOutput(text=result.get("summary", ""), data=result)
