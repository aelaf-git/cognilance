"""GitHub read tool. A missing connection is reported before any API call."""

from __future__ import annotations

import json
from typing import Any

from tools.registry import ToolContext, ToolOutput

_ACTIONS = ("list_commits", "list_pull_requests", "list_issues", "get_repo")

_EMPTY = {
    "list_commits": "No commits.",
    "list_pull_requests": "No pull requests.",
    "list_issues": "No issues.",
    "get_repo": "No repository.",
}


def _instruction_params(instruction: str, params: dict[str, Any]) -> dict[str, Any]:
    body = dict(params or {})
    text = str(instruction or "").strip()
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            body = {**parsed, **body}
    body.pop("organization_id", None)
    return body


def _http_status(result: Any) -> int | None:
    if not isinstance(result, dict):
        return None
    raw = result.get("http_status")
    if raw in (None, ""):
        return None
    try:
        code = int(raw)
    except (TypeError, ValueError):
        return None
    if code >= 400:
        return code
    return None


def _error_output(code: int) -> ToolOutput:
    message = f"GitHub API error {code}"
    return ToolOutput(
        text=message,
        data={"status_code": code, "error": message},
        status="error",
    )


def _selected_ids(user_id: str) -> list[str]:
    from core.broker.store import IntegrationStore
    from core.broker.token_manager import github_organization

    organization_id = github_organization(user_id)
    if not organization_id:
        return []
    store = IntegrationStore()
    store.init_db()
    grant = store.get_org_grant(organization_id, "github")
    if grant is None:
        return []
    return [str(repo_id) for repo_id in grant.selected_repos if str(repo_id).strip()]


def _owner_repo(row: dict[str, Any]) -> tuple[str, str]:
    full_name = str(row.get("full_name") or "")
    if "/" in full_name:
        owner, repo = full_name.split("/", 1)
        return owner.strip(), repo.strip()
    owner_row = row.get("owner")
    owner = ""
    if isinstance(owner_row, dict):
        owner = str(owner_row.get("login") or "").strip()
    return owner, str(row.get("name") or "").strip()


def _item(row: dict[str, Any]) -> dict[str, Any]:
    commit = row.get("commit") if isinstance(row.get("commit"), dict) else {}
    message = str(commit.get("message") or "")
    title = str(
        row.get("title")
        or row.get("full_name")
        or (message.split("\n", 1)[0] if message else "")
        or row.get("name")
        or ""
    )
    committer = commit.get("committer") if isinstance(commit.get("committer"), dict) else {}
    updated = str(row.get("updated_at") or committer.get("date") or row.get("pushed_at") or "")
    ident = row.get("sha") or row.get("id") or row.get("number") or ""
    return {
        "id": str(ident),
        "url": str(row.get("html_url") or ""),
        "title": title,
        "updated_at": updated,
        "raw": row,
    }


def _rows(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [row for row in result if isinstance(row, dict)]
    if isinstance(result, dict) and _http_status(result) is None:
        return [result]
    return []


async def _call(ctx: ToolContext, action: str, params: dict[str, Any]) -> tuple[Any, int | None]:
    result = await ctx.client.run(ctx.user_id, "github", action, params)
    return result, _http_status(result)


async def _repo_by_id(ctx: ToolContext, repo_id: str) -> tuple[dict[str, Any] | None, int | None]:
    result, code = await _call(ctx, "get_repo", {"repo_id": repo_id})
    if code:
        return None, code
    if isinstance(result, dict):
        return result, None
    return None, None


async def _resolve_repo(
    ctx: ToolContext, body: dict[str, Any], selected: list[str]
) -> tuple[str, str, dict[str, Any] | None, int | None]:
    owner = str(body.get("owner") or "").strip()
    repo = str(body.get("repo") or "").strip()
    requested = str(body.get("repo_id") or body.get("id") or "").strip()
    chosen: dict[str, Any] | None = None
    allowed = set(selected)

    if owner and repo and selected:
        probed, code = await _call(ctx, "get_repo", {"owner": owner, "repo": repo})
        if code:
            return "", "", None, code
        identity = str(probed.get("id") or "") if isinstance(probed, dict) else ""
        if identity in allowed:
            chosen = probed if isinstance(probed, dict) else None
        else:
            owner, repo = "", ""

    if (not owner or not repo) and selected:
        target = requested if requested in allowed else selected[0]
        chosen, code = await _repo_by_id(ctx, target)
        if code:
            return "", "", None, code
        if chosen is not None:
            owner, repo = _owner_repo(chosen)
    elif requested and not owner and not selected:
        chosen, code = await _repo_by_id(ctx, requested)
        if code:
            return "", "", None, code
        if chosen is not None:
            owner, repo = _owner_repo(chosen)
    return owner, repo, chosen, None


async def run(
    action: str,
    *,
    instruction: str,
    params: dict[str, Any],
    ctx: ToolContext,
) -> ToolOutput:
    if action not in _ACTIONS:
        raise RuntimeError(f"Unknown github action: {action}")
    if not ctx.client.is_connected(ctx.user_id, "github"):
        raise RuntimeError("GitHub is not connected")
    body = _instruction_params(instruction, params)
    owner, repo, chosen, code = await _resolve_repo(ctx, body, _selected_ids(ctx.user_id))
    if code:
        return _error_output(code)
    if not owner or not repo:
        raise RuntimeError("owner and repo are required")

    if action == "get_repo" and chosen is not None:
        result: Any = chosen
    else:
        call_params: dict[str, Any] = {"owner": owner, "repo": repo}
        if body.get("per_page"):
            call_params["per_page"] = body.get("per_page")
        result, code = await _call(ctx, action, call_params)
        if code:
            return _error_output(code)

    items = [_item(row) for row in _rows(result)]
    if not items:
        summary = _EMPTY.get(action, "No results.")
    else:
        summary = "\n".join(
            f"- {item['title']} {item['url']} {item['updated_at']}".strip() for item in items
        )
    return ToolOutput(text=summary, data={"items": items})
