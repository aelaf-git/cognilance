"""Third-party API action handlers for connected integrations."""

from __future__ import annotations

import base64
import json
from email.mime.text import MIMEText
from typing import Any

import httpx

from orchestrator.integrations.registry import INTEGRATIONS


class IntegrationExecutor:
    async def execute(
        self,
        integration_id: str,
        access_token: str,
        action: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        spec = INTEGRATIONS.get(integration_id)
        if not spec:
            raise RuntimeError(f"Unknown integration: {integration_id}")
        if action not in spec["actions"]:
            raise RuntimeError(f"Unsupported action '{action}' for {integration_id}")

        handler = getattr(self, f"_action_{integration_id.replace('-', '_')}", None)
        if not handler:
            raise RuntimeError(f"No handler for {integration_id}")
        return await handler(access_token, action, params)

    async def _google_request(
        self,
        token: str,
        method: str,
        url: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        content: bytes | None = None,
        headers: dict | None = None,
    ) -> Any:
        req_headers = {"Authorization": f"Bearer {token}", **(headers or {})}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method,
                url,
                headers=req_headers,
                json=json_body,
                params=params,
                content=content,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"Google API error {response.status_code}: {response.text}")
            if response.content:
                return response.json() if "application/json" in response.headers.get(
                    "content-type", ""
                ) else response.text
            return {}

    async def _action_google_drive(
        self, token: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if action == "list_files":
            data = await self._google_request(
                token,
                "GET",
                "https://www.googleapis.com/drive/v3/files",
                params={
                    "pageSize": int(params.get("page_size", 20)),
                    "fields": "files(id,name,mimeType,modifiedTime)",
                    "q": params.get("query", ""),
                },
            )
            return {"files": data.get("files", [])}

        if action == "read_file":
            file_id = str(params.get("file_id", "")).strip()
            if not file_id:
                raise RuntimeError("file_id is required")
            meta = await self._google_request(
                token,
                "GET",
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": "id,name,mimeType"},
            )
            mime = meta.get("mimeType", "")
            if mime.startswith("application/vnd.google-apps."):
                export_mime = "text/plain"
                content = await self._google_request(
                    token,
                    "GET",
                    f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
                    params={"mimeType": export_mime},
                )
            else:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(
                        f"https://www.googleapis.com/drive/v3/files/{file_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"alt": "media"},
                    )
                    if response.status_code >= 400:
                        raise RuntimeError(response.text)
                    content = response.text
            return {"file_id": file_id, "name": meta.get("name"), "content": content}

        if action == "create_file":
            name = str(params.get("name", "Untitled")).strip()
            content = str(params.get("content", ""))
            metadata = {"name": name, "mimeType": "text/plain"}
            body = (
                f"--boundary\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{json.dumps(metadata)}\r\n"
                f"--boundary\r\nContent-Type: text/plain\r\n\r\n"
                f"{content}\r\n--boundary--"
            ).encode()
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "multipart/related; boundary=boundary",
                    },
                    content=body,
                )
                if response.status_code >= 400:
                    raise RuntimeError(response.text)
                return response.json()

        if action == "upload_file":
            name = str(params.get("name", "upload.txt")).strip()
            content = str(params.get("content", ""))
            metadata = {"name": name}
            body = (
                f"--boundary\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{json.dumps(metadata)}\r\n"
                f"--boundary\r\nContent-Type: application/octet-stream\r\n\r\n"
                f"{content}\r\n--boundary--"
            ).encode()
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "multipart/related; boundary=boundary",
                    },
                    content=body,
                )
                if response.status_code >= 400:
                    raise RuntimeError(response.text)
                return response.json()

        if action == "create_document":
            name = str(params.get("name", "Untitled")).strip() or "Untitled"
            content = str(params.get("content", params.get("body", "")))
            style = params.get("style") if isinstance(params.get("style"), dict) else None
            data = await self._google_request(
                token,
                "POST",
                "https://www.googleapis.com/drive/v3/files",
                json_body={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.document",
                },
            )
            document_id = str(data.get("id", "")).strip()
            if content and document_id:
                await self._docs_write_styled(
                    token, document_id, content, index=1, style=style
                )
            return {
                "document_id": document_id,
                "name": name,
                "url": f"https://docs.google.com/document/d/{document_id}/edit",
                "content_written": bool(content),
                "styled": bool(style),
            }

        if action == "read_document":
            document_id = str(
                params.get("document_id", params.get("file_id", ""))
            ).strip()
            if not document_id:
                raise RuntimeError("document_id is required")
            doc = await self._google_request(
                token,
                "GET",
                f"https://docs.googleapis.com/v1/documents/{document_id}",
            )
            return {
                "document_id": document_id,
                "title": doc.get("title"),
                "text": self._docs_extract_text(doc),
                "url": f"https://docs.google.com/document/d/{document_id}/edit",
            }

        if action == "write_document":
            document_id = str(
                params.get("document_id", params.get("file_id", ""))
            ).strip()
            content = str(params.get("content", params.get("body", "")))
            style = params.get("style") if isinstance(params.get("style"), dict) else None
            if not document_id:
                raise RuntimeError("document_id is required")
            if not content:
                raise RuntimeError("content is required")
            mode = str(params.get("mode", "append")).strip().lower()
            if mode == "replace":
                doc = await self._google_request(
                    token,
                    "GET",
                    f"https://docs.googleapis.com/v1/documents/{document_id}",
                )
                end_index = self._docs_end_index(doc)
                requests: list[dict[str, Any]] = []
                if end_index > 1:
                    requests.append(
                        {
                            "deleteContentRange": {
                                "range": {"startIndex": 1, "endIndex": end_index}
                            }
                        }
                    )
                requests.extend(
                    self._docs_write_requests(content, index=1, style=style)
                )
                await self._google_request(
                    token,
                    "POST",
                    f"https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate",
                    json_body={"requests": requests},
                )
            else:
                doc = await self._google_request(
                    token,
                    "GET",
                    f"https://docs.googleapis.com/v1/documents/{document_id}",
                )
                insert_index = max(1, self._docs_end_index(doc) - 1)
                if insert_index > 1 and not content.startswith("\n"):
                    content = f"\n{content}"
                await self._docs_write_styled(
                    token, document_id, content, index=insert_index, style=style
                )
            return {
                "document_id": document_id,
                "mode": mode,
                "url": f"https://docs.google.com/document/d/{document_id}/edit",
                "chars_written": len(content),
                "styled": bool(style),
            }

        raise RuntimeError(f"Unhandled action: {action}")

    @staticmethod
    def _docs_end_index(doc: dict[str, Any]) -> int:
        end_index = 1
        for element in doc.get("body", {}).get("content", []):
            if "endIndex" in element:
                end_index = element["endIndex"]
        return end_index

    @staticmethod
    def _docs_extract_text(doc: dict[str, Any]) -> str:
        parts: list[str] = []
        for element in doc.get("body", {}).get("content", []):
            paragraph = element.get("paragraph")
            if not paragraph:
                continue
            for elem in paragraph.get("elements", []):
                text_run = elem.get("textRun")
                if text_run and text_run.get("content"):
                    parts.append(text_run["content"])
        return "".join(parts).strip()

    @staticmethod
    def _docs_style_requests(
        start_index: int, end_index: int, style: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        if not style or end_index <= start_index:
            return []
        text_style: dict[str, Any] = {}
        fields: list[str] = []
        if style.get("bold"):
            text_style["bold"] = True
            fields.append("bold")
        font_size = style.get("font_size")
        if font_size is not None:
            text_style["fontSize"] = {"magnitude": float(font_size), "unit": "PT"}
            fields.append("fontSize")
        font_family = style.get("font_family")
        if font_family:
            text_style["weightedFontFamily"] = {"fontFamily": str(font_family)}
            fields.append("weightedFontFamily")
        if not fields:
            return []
        return [
            {
                "updateTextStyle": {
                    "range": {"startIndex": start_index, "endIndex": end_index},
                    "textStyle": text_style,
                    "fields": ",".join(fields),
                }
            }
        ]

    @classmethod
    def _docs_write_requests(
        cls,
        text: str,
        *,
        index: int,
        style: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = [
            {"insertText": {"location": {"index": index}, "text": text}}
        ]
        requests.extend(cls._docs_style_requests(index, index + len(text), style))
        return requests

    async def _docs_write_styled(
        self,
        token: str,
        document_id: str,
        text: str,
        *,
        index: int = 1,
        style: dict[str, Any] | None = None,
    ) -> None:
        await self._google_request(
            token,
            "POST",
            f"https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate",
            json_body={"requests": self._docs_write_requests(text, index=index, style=style)},
        )

    async def _docs_insert_text(
        self, token: str, document_id: str, text: str, *, index: int = 1
    ) -> None:
        await self._google_request(
            token,
            "POST",
            f"https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate",
            json_body={
                "requests": [
                    {"insertText": {"location": {"index": index}, "text": text}}
                ]
            },
        )

    async def _action_gmail(
        self, token: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        base = "https://gmail.googleapis.com/gmail/v1/users/me"

        if action == "list_emails":
            data = await self._google_request(
                token,
                "GET",
                f"{base}/messages",
                params={"maxResults": int(params.get("max_results", 10))},
            )
            message_refs = data.get("messages", []) or []
            emails: list[dict[str, Any]] = []
            for ref in message_refs[: int(params.get("max_results", 10))]:
                msg_id = ref.get("id")
                if not msg_id:
                    continue
                detail = await self._google_request(
                    token,
                    "GET",
                    f"{base}/messages/{msg_id}",
                    params={
                        "format": "metadata",
                        "metadataHeaders": ["Subject", "From", "Date"],
                    },
                )
                headers = {
                    h["name"]: h["value"]
                    for h in detail.get("payload", {}).get("headers", [])
                    if h.get("name") in {"Subject", "From", "Date"}
                }
                emails.append(
                    {
                        "id": msg_id,
                        "subject": headers.get("Subject", "(no subject)"),
                        "from": headers.get("From", ""),
                        "date": headers.get("Date", ""),
                        "snippet": detail.get("snippet", ""),
                    }
                )
            return {"emails": emails, "count": len(emails)}

        if action == "read_email":
            msg_id = str(params.get("message_id", "")).strip()
            if not msg_id:
                raise RuntimeError("message_id is required")
            data = await self._google_request(token, "GET", f"{base}/messages/{msg_id}", params={"format": "full"})
            return data

        if action == "search_emails":
            query = str(params.get("query", "")).strip()
            if not query:
                raise RuntimeError("query is required")
            data = await self._google_request(
                token,
                "GET",
                f"{base}/messages",
                params={"q": query, "maxResults": int(params.get("max_results", 10))},
            )
            return {"messages": data.get("messages", []), "query": query}

        if action == "send_email":
            to_addr = str(params.get("to", "")).strip()
            subject = str(params.get("subject", "Message from Cognilance"))
            body = str(params.get("body", params.get("content", "")))
            if not to_addr:
                raise RuntimeError("to is required")
            message = MIMEText(body)
            message["to"] = to_addr
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            data = await self._google_request(
                token,
                "POST",
                f"{base}/messages/send",
                json_body={"raw": raw},
            )
            return data
        raise RuntimeError(f"Unhandled action: {action}")

    async def _action_google_calendar(
        self, token: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        calendar_id = str(params.get("calendar_id", "primary"))
        base = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}"

        if action == "list_events":
            data = await self._google_request(
                token,
                "GET",
                f"{base}/events",
                params={
                    "maxResults": int(params.get("max_results", 10)),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "timeMin": params.get("time_min"),
                },
            )
            return {"events": data.get("items", [])}

        if action == "create_event":
            summary = str(params.get("summary", "New event"))
            start = params.get("start") or params.get("start_time")
            end = params.get("end") or params.get("end_time")
            if not start or not end:
                raise RuntimeError("start and end are required")
            event = {
                "summary": summary,
                "start": start if isinstance(start, dict) else {"dateTime": str(start)},
                "end": end if isinstance(end, dict) else {"dateTime": str(end)},
                "description": params.get("description", ""),
            }
            data = await self._google_request(token, "POST", f"{base}/events", json_body=event)
            return data

        if action == "delete_event":
            event_id = str(params.get("event_id", "")).strip()
            if not event_id:
                raise RuntimeError("event_id is required")
            await self._google_request(token, "DELETE", f"{base}/events/{event_id}")
            return {"deleted": True, "event_id": event_id}
        raise RuntimeError(f"Unhandled action: {action}")

    async def _action_notion(
        self, token: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            if action == "list_databases":
                response = await client.post(
                    "https://api.notion.com/v1/search",
                    headers=headers,
                    json={"filter": {"value": "database", "property": "object"}},
                )
            elif action == "query_database":
                db_id = str(params.get("database_id", "")).strip()
                if not db_id:
                    raise RuntimeError("database_id is required")
                response = await client.post(
                    f"https://api.notion.com/v1/databases/{db_id}/query",
                    headers=headers,
                    json={"page_size": int(params.get("page_size", 10))},
                )
            elif action == "create_page":
                parent = params.get("parent") or {"database_id": params.get("database_id")}
                properties = params.get("properties") or {
                    "Name": {"title": [{"text": {"content": str(params.get("title", "New page"))}}]}
                }
                response = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers=headers,
                    json={"parent": parent, "properties": properties},
                )
            elif action == "update_page":
                page_id = str(params.get("page_id", "")).strip()
                if not page_id:
                    raise RuntimeError("page_id is required")
                response = await client.patch(
                    f"https://api.notion.com/v1/pages/{page_id}",
                    headers=headers,
                    json={"properties": params.get("properties", {})},
                )
            else:
                raise RuntimeError(f"Unhandled action: {action}")
            if response.status_code >= 400:
                raise RuntimeError(f"Notion API error: {response.text}")
            return response.json()

    async def _action_slack(
        self, token: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            if action == "list_channels":
                response = await client.get(
                    "https://slack.com/api/conversations.list",
                    headers=headers,
                    params={"limit": int(params.get("limit", 20)), "types": "public_channel,private_channel"},
                )
            elif action == "read_messages":
                channel = str(params.get("channel_id", "")).strip()
                if not channel:
                    raise RuntimeError("channel_id is required")
                response = await client.get(
                    "https://slack.com/api/conversations.history",
                    headers=headers,
                    params={"channel": channel, "limit": int(params.get("limit", 20))},
                )
            elif action == "send_message":
                channel = str(params.get("channel_id", "")).strip()
                text = str(params.get("text", params.get("message", ""))).strip()
                if not channel or not text:
                    raise RuntimeError("channel_id and text are required")
                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers=headers,
                    json={"channel": channel, "text": text},
                )
            elif action == "search_messages":
                query = str(params.get("query", "")).strip()
                if not query:
                    raise RuntimeError("query is required")
                response = await client.get(
                    "https://slack.com/api/search.messages",
                    headers=headers,
                    params={"query": query, "count": int(params.get("limit", 10))},
                )
            else:
                raise RuntimeError(f"Unhandled action: {action}")
            data = response.json()
            if not data.get("ok", True) and response.status_code >= 400:
                raise RuntimeError(data.get("error", response.text))
            if isinstance(data, dict) and data.get("ok") is False:
                raise RuntimeError(data.get("error", "Slack API error"))
            return data

    async def _action_github(
        self, token: str, action: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            if action == "list_repositories":
                response = await client.get(
                    "https://api.github.com/user/repos",
                    headers=headers,
                    params={"per_page": int(params.get("per_page", 20))},
                )
            elif action == "list_issues":
                owner = str(params.get("owner", "")).strip()
                repo = str(params.get("repo", "")).strip()
                if not owner or not repo:
                    raise RuntimeError("owner and repo are required")
                response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/issues",
                    headers=headers,
                    params={"state": "open", "per_page": int(params.get("per_page", 20))},
                )
            elif action == "create_issue":
                owner = str(params.get("owner", "")).strip()
                repo = str(params.get("repo", "")).strip()
                title = str(params.get("title", "")).strip()
                if not owner or not repo or not title:
                    raise RuntimeError("owner, repo, and title are required")
                response = await client.post(
                    f"https://api.github.com/repos/{owner}/{repo}/issues",
                    headers=headers,
                    json={"title": title, "body": params.get("body", "")},
                )
            elif action == "list_pull_requests":
                owner = str(params.get("owner", "")).strip()
                repo = str(params.get("repo", "")).strip()
                if not owner or not repo:
                    raise RuntimeError("owner and repo are required")
                response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/pulls",
                    headers=headers,
                    params={"state": "open", "per_page": int(params.get("per_page", 20))},
                )
            elif action == "read_file":
                owner = str(params.get("owner", "")).strip()
                repo = str(params.get("repo", "")).strip()
                path = str(params.get("path", "")).strip()
                if not owner or not repo or not path:
                    raise RuntimeError("owner, repo, and path are required")
                response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
                    headers=headers,
                )
            else:
                raise RuntimeError(f"Unhandled action: {action}")
            if response.status_code >= 400:
                raise RuntimeError(f"GitHub API error {response.status_code}: {response.text}")
            data = response.json()
            if action == "read_file" and isinstance(data, dict) and data.get("content"):
                decoded = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                data = {**data, "decoded_content": decoded}
            return data
