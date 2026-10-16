"""Conversations, their sessions/subscriptions, and notification streams."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.deps import conv_store, mission_store, sub_store, user_from
from api.sse import sse_line, sse_response
from core.context.drafts.store import DraftStore
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
    conversation = conv_store.get_conversation(conversation_id, user_id=user_from(request))
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def _sessions_for(conversation_id: str) -> list[dict[str, Any]]:
    return [
        enrich_session_dict(m, sub_store=sub_store)
        for m in mission_store.list_missions_for_conversation(conversation_id, limit=50)
    ]


@router.get("/conversations")
async def list_conversations(request: Request) -> JSONResponse:
    conversations = []
    for c in conv_store.list_conversations(limit=50, user_id=user_from(request)):
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
    conversation = conv_store.create_conversation(user_id=user_from(request))
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
async def get_conversation(conversation_id: str, request: Request) -> JSONResponse:
    conversation = _require_conversation(conversation_id, request)
    messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
            "ui": _parse_message_ui(m.ui),
        }
        for m in conv_store.list_messages(conversation_id, limit=200)
    ]
    return JSONResponse(
        content={
            "id": conversation.id,
            "title": conv_store.display_title(conversation),
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": messages,
            "sessions": _sessions_for(conversation_id),
            "active_listeners": [
                s.to_dict() for s in sub_store.list_active_for_conversation(conversation_id)
            ],
            "active_doc": DraftStore().get_active_doc(conversation_id),
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
        content={"sessions": _sessions_for(conversation_id), "conversation_id": conversation_id}
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

    sub = sub_store.get_subscription(subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    user_id = user_from(request)
    if sub.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    service = SubscriptionService(sub_store=sub_store, conv_store=conv_store)
    result = await service.unsubscribe_gmail_inbox(
        user_id, conversation_id=sub.conversation_id, subscription_id=subscription_id
    )
    return JSONResponse(content=result)
