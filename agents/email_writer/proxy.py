"""HTTP client for orchestrator Gmail tool proxy callbacks."""

from __future__ import annotations

from typing import Any

import httpx


class OrchestratorProxyError(Exception):
    pass


def _ctx(task_data: dict[str, Any]) -> dict[str, Any]:
    ctx = task_data.get("orchestrator") or {}
    if not ctx.get("callback_token") or not ctx.get("base_url"):
        raise OrchestratorProxyError(
            "Missing orchestrator callback context — agent must be hired by the orchestrator"
        )
    return ctx


async def gmail_send(
    task_data: dict[str, Any],
    *,
    to: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    ctx = _ctx(task_data)
    url = f"{ctx['base_url'].rstrip('/')}/tools/gmail/send"
    payload = {
        "task_id": ctx["task_id"],
        "params": {"to": to, "subject": subject, "body": body},
    }
    return await _post(url, ctx["callback_token"], payload)


async def gmail_list(
    task_data: dict[str, Any],
    *,
    max_results: int = 10,
) -> dict[str, Any]:
    ctx = _ctx(task_data)
    url = f"{ctx['base_url'].rstrip('/')}/tools/gmail/list"
    payload = {"task_id": ctx["task_id"], "params": {"max_results": max_results}}
    return await _post(url, ctx["callback_token"], payload)


async def gmail_search(
    task_data: dict[str, Any],
    *,
    query: str,
    max_results: int = 10,
) -> dict[str, Any]:
    ctx = _ctx(task_data)
    url = f"{ctx['base_url'].rstrip('/')}/tools/gmail/search"
    payload = {
        "task_id": ctx["task_id"],
        "params": {"query": query, "max_results": max_results},
    }
    return await _post(url, ctx["callback_token"], payload)


async def _post(url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code >= 400:
        detail = resp.text
        try:
            body = resp.json()
            if isinstance(body, dict) and body.get("detail"):
                detail = str(body["detail"])
        except ValueError:
            pass
        raise OrchestratorProxyError(detail)
    data = resp.json()
    return data if isinstance(data, dict) else {"result": data}
