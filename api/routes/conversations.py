"""Conversations, their sessions/subscriptions, and notification streams."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.deps import (
    account_display_name,
    active_organization_id,
    can_read_conversation,
    conv_store,
    mission_store,
    organization_ids_for,
    owner_filter,
    sub_store,
    user_from,
)
from api.sse import sse_line, sse_response
from core.context.drafts.store import DraftStore
from tools.docx.store import active_document_id
from core.context.subscriptions.session_sync import enrich_session_dict

router = APIRouter()


def _parse_message_ui(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) and parsed.get("name") else None


def _require_conversation(conversation_id: str, request: Request):
    account_id = user_from(request)
    conversation = conv_store.get_conversation(conversation_id)
    if conversation is None or not can_read_conversation(account_id, conversation):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _author_name(role: str, author_id: str | None) -> str | None:
    if role == "assistant":
        return "Cognilance"
    if not author_id:
        return None
    return account_display_name(author_id)


def _sessions_for(conversation_id: str, request: Request) -> list[dict[str, Any]]:
    return [
        enrich_session_dict(m, sub_store=sub_store)
        for m in mission_store.list_missions_for_conversation(
            conversation_id, limit=50, **owner_filter(user_from(request))
        )
    ]


@router.get("/conversations")
async def list_conversations(request: Request) -> JSONResponse:
    account_id = user_from(request)
    organization_ids = organization_ids_for(account_id)
    if organization_ids:
        listed = conv_store.list_conversations(limit=50, organization_ids=organization_ids)
    else:
        listed = conv_store.list_conversations(limit=50, user_id=account_id)
    conversations = []
    for c in listed:
        stats = conv_store.session_stats(c.id)
        conversations.append(
            {
                "id": c.id,
                "title": conv_store.display_title(c),
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
                "session_count": stats["session_count"],
                "latest_status": stats["latest_status"],
                "active_listeners": [
                    s.to_dict() for s in sub_store.list_active_for_conversation(c.id)
                ],
            }
        )
    return JSONResponse(content={"conversations": conversations})


@router.post("/conversations")
async def create_conversation(request: Request) -> JSONResponse:
    user_id = user_from(request)
    conversation = conv_store.create_conversation(
        user_id=user_id,
        organization_id=active_organization_id(user_id),
    )
    return JSONResponse(
        content={
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "session_count": 0,
            "latest_status": None,
        }
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
    before: int | None = Query(default=None),
) -> JSONResponse:
    conversation = _require_conversation(conversation_id, request)
    messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
            "ui": _parse_message_ui(m.ui),
            "author_id": m.author_id,
            "author_name": _author_name(m.role, m.author_id),
        }
        for m in conv_store.list_messages(conversation_id, limit=200, before=before)
    ]
    return JSONResponse(
        content={
            "id": conversation.id,
            "title": conv_store.display_title(conversation),
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": messages,
            "sessions": _sessions_for(conversation_id, request),
            "active_listeners": [
                s.to_dict() for s in sub_store.list_active_for_conversation(conversation_id)
            ],
            "active_doc": DraftStore().get_active_doc(conversation_id),
            "active_docx": active_document_id(conversation_id),
        }
    )


@router.get("/conversations/{conversation_id}/active-doc")
async def get_conversation_active_doc(conversation_id: str, request: Request) -> JSONResponse:
    _require_conversation(conversation_id, request)
    return JSONResponse(
        content={
            "conversation_id": conversation_id,
            "active_doc": DraftStore().get_active_doc(conversation_id),
        }
    )


@router.get("/conversations/{conversation_id}/sessions")
async def list_conversation_sessions(conversation_id: str, request: Request) -> JSONResponse:
    _require_conversation(conversation_id, request)
    return JSONResponse(
        content={
            "sessions": _sessions_for(conversation_id, request),
            "conversation_id": conversation_id,
        }
    )


@router.delete("/conversations/{conversation_id}")
@router.post("/conversations/{conversation_id}/delete")
async def delete_conversation(conversation_id: str, request: Request) -> JSONResponse:
    _require_conversation(conversation_id, request)
    removed = mission_store.delete_missions_for_conversation(conversation_id)
    sub_store.stop_for_conversation(conversation_id)
    conv_store.delete_conversation(conversation_id)
    return JSONResponse(
        content={"conversation_id": conversation_id, "deleted": True, "sessions_removed": removed}
    )


@router.get("/conversations/{conversation_id}/subscriptions")
async def list_conversation_subscriptions(conversation_id: str, request: Request) -> JSONResponse:
    _require_conversation(conversation_id, request)
    subs = [s.to_dict() for s in sub_store.list_active_for_conversation(conversation_id)]
    return JSONResponse(content={"subscriptions": subs, "conversation_id": conversation_id})


@router.get("/conversations/{conversation_id}/notifications")
async def conversation_notifications(conversation_id: str, request: Request) -> StreamingResponse:
    _require_conversation(conversation_id, request)
    after_id = int(request.query_params.get("after", "0") or "0")

    async def stream() -> AsyncIterator[str]:
        nonlocal after_id
        while True:
            for note in sub_store.list_notifications(conversation_id, after_id=after_id):
                after_id = int(note["id"])
                yield sse_line(note)
            await asyncio.sleep(2)

    return sse_response(stream())


@router.post("/subscriptions/{subscription_id}/stop")
async def stop_subscription(subscription_id: str, request: Request) -> JSONResponse:
    from core.context.subscriptions.service import SubscriptionService

    user_id = user_from(request)
    sub = sub_store.get_subscription(subscription_id, **owner_filter(user_id))
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    service = SubscriptionService(sub_store=sub_store, conv_store=conv_store)
    result = await service.unsubscribe_gmail_inbox(
        user_id, conversation_id=sub.conversation_id, subscription_id=subscription_id
    )
    return JSONResponse(content=result)
