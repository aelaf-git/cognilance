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


async def docs_read(
    task_data: dict[str, Any],
    *,
    document_id: str,
) -> dict[str, Any]:
    ctx = _ctx(task_data)
    url = f"{ctx['base_url'].rstrip('/')}/tools/docs/read"
    payload = {
        "task_id": ctx["task_id"],
        "params": {"document_id": document_id},
    }
    return await _post(url, ctx["callback_token"], payload)


async def docs_batch_update(
    task_data: dict[str, Any],
    *,
    document_id: str,
    requests: list[dict[str, Any]],
) -> dict[str, Any]:
    ctx = _ctx(task_data)
    url = f"{ctx['base_url'].rstrip('/')}/tools/docs/batch_update"
    payload = {
        "task_id": ctx["task_id"],
        "params": {"document_id": document_id, "requests": requests},
    }
    return await _post(url, ctx["callback_token"], payload)


async def docs_export(
    task_data: dict[str, Any],
    *,
    document_id: str,
    mime_type: str = "text/plain",
) -> dict[str, Any]:
    ctx = _ctx(task_data)
    url = f"{ctx['base_url'].rstrip('/')}/tools/docs/export"
    payload = {
        "task_id": ctx["task_id"],
        "params": {"document_id": document_id, "mime_type": mime_type},
    }
    return await _post(url, ctx["callback_token"], payload)


async def docs_insert_table(
    task_data: dict[str, Any],
    *,
    document_id: str,
    headers: list[str],
    rows: list[list[str]],
    index: int | None = None,
) -> dict[str, Any]:
    ctx = _ctx(task_data)
    url = f"{ctx['base_url'].rstrip('/')}/tools/docs/insert_table"
    params: dict[str, Any] = {
        "document_id": document_id,
        "headers": headers,
        "rows": rows,
    }
    if index is not None:
        params["index"] = index
    payload = {"task_id": ctx["task_id"], "params": params}
    return await _post(url, ctx["callback_token"], payload)


async def docs_insert_image(
    task_data: dict[str, Any],
    *,
    document_id: str,
    content_base64: str | None = None,
    url: str | None = None,
    drive_file_id: str | None = None,
    mime_type: str = "image/png",
    name: str = "chart.png",
    width_pt: float = 400,
    index: int | None = None,
) -> dict[str, Any]:
    ctx = _ctx(task_data)
    endpoint = f"{ctx['base_url'].rstrip('/')}/tools/docs/insert_image"
    params: dict[str, Any] = {
        "document_id": document_id,
        "mime_type": mime_type,
        "name": name,
        "width_pt": width_pt,
    }
    if content_base64:
        params["content_base64"] = content_base64
    if url:
        params["url"] = url
    if drive_file_id:
        params["drive_file_id"] = drive_file_id
    if index is not None:
        params["index"] = index
    payload = {"task_id": ctx["task_id"], "params": params}
    return await _post(endpoint, ctx["callback_token"], payload)


async def _post(url: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=120.0) as client:
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
