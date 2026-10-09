"""HTTP client for orchestrator Google Docs tool proxy callbacks."""

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


async def docs_create(
    task_data: dict[str, Any],
    *,
    name: str,
    content: str = "",
) -> dict[str, Any]:
    ctx = _ctx(task_data)
    url = f"{ctx['base_url'].rstrip('/')}/tools/docs/create"
    payload = {
        "task_id": ctx["task_id"],
        "params": {"name": name, "content": content},
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
