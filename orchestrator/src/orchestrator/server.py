"""FastAPI server for the orchestrator agent."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncIterator

from cognilance.assets import LOGO_PATH
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from langchain_core.messages import HumanMessage

from orchestrator.auth.session import get_user_id, resolve_user_id, set_user_cookie
from orchestrator.context import current_conversation_id, current_mission_id, current_user_id, current_user_timezone
from orchestrator.graph import ensure_graph, init_graph
from orchestrator.integrations.oauth import OAuthService
from orchestrator.conversations.store import ConversationStore
from orchestrator.mission_runner import stream_mission_graph
from orchestrator.missions.finalize import finalize_session_status
from orchestrator.missions.session_type import SessionType
from orchestrator.missions.models import MissionStatus
from orchestrator.missions.store import MissionStore
from orchestrator.subscriptions.store import SubscriptionStore
from orchestrator.subscriptions.session_sync import enrich_session_dict, stop_listener_for_mission
from orchestrator.subscriptions.ticker import tick_subscriptions
from orchestrator.users.timezone import activate_user_timezone, client_timezone_from_request
from orchestrator.ui.chat import orchestrator_chat_html
from orchestrator.apps.store import init_all_stores


def _thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _ui_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": item["name"], "props": item.get("props") or {}}
        for item in (result.get("ui") or [])
        if item.get("type") == "ui" and item.get("name") != "text-card"
    ]


def create_app() -> FastAPI:
    store = MissionStore()
    conv_store = ConversationStore()
    sub_store = SubscriptionStore()
    store.init_db()
    sub_store.init_db()
    init_all_stores()
    oauth_service = OAuthService()

    app = FastAPI(
        title="Cognilance Orchestrator Agent",
        description="Autonomous agent with missions, OAuth integrations, and marketplace hiring",
        version="0.3.0",
    )

    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        user_id = get_user_id(request) or resolve_user_id(request)
        request.state.user_id = user_id
        user_token = current_user_id.set(user_id)
        tz_token = activate_user_timezone(
            user_id,
            from_client=client_timezone_from_request(request),
        )
        try:
            response = await call_next(request)
        finally:
            current_user_timezone.reset(tz_token)
            current_user_id.reset(user_token)
        if not get_user_id(request):
            set_user_cookie(response, user_id)
        return response

    @app.on_event("startup")
    async def on_startup() -> None:
        store.init_db()
        sub_store.init_db()
        init_all_stores()
        recovered = store.recover_stale_running()
        if recovered:
            print(f"Recovered {recovered} stale running mission(s)", flush=True)
        await init_graph()

        async def subscription_ticker_loop() -> None:
            while True:
                try:
                    await tick_subscriptions()
                except Exception as exc:
                    print(f"Subscription ticker error: {exc}", flush=True)
                await asyncio.sleep(5)

        asyncio.create_task(subscription_ticker_loop())

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/logo.png")
    async def logo() -> FileResponse:
        if not LOGO_PATH.is_file():
            raise HTTPException(status_code=404, detail="Logo not found")
        return FileResponse(LOGO_PATH, media_type="image/png")

    @app.get("/chat", response_class=HTMLResponse)
    @app.get("/integrations", response_class=HTMLResponse)
    async def spa_page() -> str:
        return orchestrator_chat_html()

    def _user(request: Request) -> str:
        return getattr(request.state, "user_id", current_user_id.get())

    @app.get("/integrations/list")
    async def list_integrations(request: Request) -> JSONResponse:
        return JSONResponse(content={"integrations": oauth_service.list_for_user(_user(request))})

    @app.get("/apps")
    async def list_apps_compat(request: Request) -> JSONResponse:
        return JSONResponse(content={"apps": oauth_service.list_for_user(_user(request))})

    @app.get("/integrations/{integration_id}/connect")
    async def connect_integration(integration_id: str, request: Request) -> RedirectResponse:
        try:
            url = oauth_service.start_oauth(_user(request), integration_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return RedirectResponse(url=url, status_code=307)

    @app.get("/integrations/oauth/callback")
    async def oauth_callback(
        request: Request,
        code: str = "",
        state: str = "",
        error: str = "",
    ) -> RedirectResponse:
        if error:
            return RedirectResponse(url=f"/integrations?error={error}", status_code=307)
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing OAuth code or state")
        try:
            _user_id, integration_id = await oauth_service.handle_callback(code, state)
        except ValueError as exc:
            return RedirectResponse(url=f"/integrations?error=invalid_state", status_code=307)
        except Exception as exc:
            return RedirectResponse(
                url=f"/integrations?error={str(exc)[:120]}",
                status_code=307,
            )
        return RedirectResponse(url=f"/integrations?connected={integration_id}", status_code=307)

    @app.post("/integrations/{integration_id}/disconnect")
    async def disconnect_integration(integration_id: str, request: Request) -> JSONResponse:
        oauth_service.disconnect(_user(request), integration_id)
        return JSONResponse(content={"integration_id": integration_id, "connected": False})

    @app.post("/apps/{app_id}/disconnect")
    async def disconnect_app_compat(app_id: str, request: Request) -> JSONResponse:
        oauth_service.disconnect(_user(request), app_id)
        return JSONResponse(content={"app_id": app_id, "connected": False})

    @app.get("/conversations")
    async def list_conversations() -> JSONResponse:
        conversations = []
        for c in conv_store.list_conversations(limit=50):
            stats = conv_store.session_stats(c.id)
            listeners = [
                s.to_dict()
                for s in sub_store.list_active_for_conversation(c.id)
            ]
            conversations.append(
                {
                    "id": c.id,
                    "title": conv_store.display_title(c),
                    "created_at": c.created_at.isoformat(),
                    "updated_at": c.updated_at.isoformat(),
                    "session_count": stats["session_count"],
                    "latest_status": stats["latest_status"],
                    "active_listeners": listeners,
                }
            )
        return JSONResponse(content={"conversations": conversations})

    @app.post("/conversations")
    async def create_conversation() -> JSONResponse:
        conversation = conv_store.create_conversation()
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

    @app.get("/conversations/{conversation_id}")
    async def get_conversation(conversation_id: str) -> JSONResponse:
        conversation = conv_store.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        messages = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in conv_store.list_messages(conversation_id, limit=200)
        ]
        sessions = [
            enrich_session_dict(m, sub_store=sub_store)
            for m in store.list_missions_for_conversation(conversation_id, limit=50)
        ]
        listeners = [s.to_dict() for s in sub_store.list_active_for_conversation(conversation_id)]
        return JSONResponse(
            content={
                "id": conversation.id,
                "title": conv_store.display_title(conversation),
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "messages": messages,
                "sessions": sessions,
                "active_listeners": listeners,
            }
        )

    @app.get("/conversations/{conversation_id}/sessions")
    async def list_conversation_sessions(conversation_id: str) -> JSONResponse:
        if not conv_store.get_conversation(conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        sessions = [
            enrich_session_dict(m, sub_store=sub_store)
            for m in store.list_missions_for_conversation(conversation_id, limit=50)
        ]
        return JSONResponse(content={"sessions": sessions, "conversation_id": conversation_id})

    @app.delete("/conversations/{conversation_id}")
    @app.post("/conversations/{conversation_id}/delete")
    async def delete_conversation(conversation_id: str) -> JSONResponse:
        if not conv_store.get_conversation(conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        removed = store.delete_missions_for_conversation(conversation_id)
        sub_store.stop_for_conversation(conversation_id)
        conv_store.delete_conversation(conversation_id)
        return JSONResponse(
            content={
                "conversation_id": conversation_id,
                "deleted": True,
                "sessions_removed": removed,
            }
        )

    @app.get("/conversations/{conversation_id}/subscriptions")
    async def list_conversation_subscriptions(conversation_id: str) -> JSONResponse:
        if not conv_store.get_conversation(conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        subs = [
            s.to_dict()
            for s in sub_store.list_active_for_conversation(conversation_id)
        ]
        return JSONResponse(content={"subscriptions": subs, "conversation_id": conversation_id})

    @app.get("/conversations/{conversation_id}/notifications")
    async def conversation_notifications(
        conversation_id: str,
        request: Request,
    ) -> StreamingResponse:
        if not conv_store.get_conversation(conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")

        after_id = int(request.query_params.get("after", "0") or "0")

        async def stream() -> AsyncIterator[str]:
            nonlocal after_id
            while True:
                notes = sub_store.list_notifications(conversation_id, after_id=after_id)
                for note in notes:
                    after_id = int(note["id"])
                    yield f"data: {json.dumps(note)}\n\n"
                await asyncio.sleep(2)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/subscriptions/{subscription_id}/stop")
    async def stop_subscription(subscription_id: str, request: Request) -> JSONResponse:
        from orchestrator.subscriptions.service import SubscriptionService

        sub = sub_store.get_subscription(subscription_id)
        if not sub:
            raise HTTPException(status_code=404, detail="Subscription not found")
        user_id = _user(request)
        if sub.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        service = SubscriptionService(sub_store=sub_store, conv_store=conv_store)
        result = await service.unsubscribe_gmail_inbox(
            user_id,
            conversation_id=sub.conversation_id,
            subscription_id=subscription_id,
        )
        return JSONResponse(content=result)

    @app.get("/sessions")
    async def list_sessions(request: Request) -> JSONResponse:
        conversation_id = str(request.query_params.get("conversation_id") or "").strip() or None
        if conversation_id:
            sessions = [
                enrich_session_dict(m, sub_store=sub_store)
                for m in store.list_missions_for_conversation(conversation_id, limit=50)
            ]
        else:
            sessions = [
                enrich_session_dict(m, sub_store=sub_store)
                for m in store.list_missions(limit=50)
            ]
        return JSONResponse(content={"sessions": sessions})

    @app.post("/sessions")
    async def create_session(request: Request) -> JSONResponse:
        payload: dict[str, Any] = await request.json()
        instruction = str(payload.get("instruction") or payload.get("text") or "").strip()
        if not instruction:
            raise HTTPException(status_code=400, detail="instruction is required")
        thread_id = str(payload.get("thread_id") or "").strip() or None
        raw_type = str(payload.get("session_type") or "").strip() or None
        session_type = SessionType(raw_type) if raw_type in {"once", "recurring"} else None
        mission = store.create_mission(
            instruction=instruction,
            thread_id=thread_id,
            session_type=session_type,
        )
        data = mission.to_session_dict()
        return JSONResponse(content=data)

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str) -> JSONResponse:
        mission = store.get_mission(session_id)
        if not mission:
            raise HTTPException(status_code=404, detail="Session not found")
        return JSONResponse(content=enrich_session_dict(mission, sub_store=sub_store))

    @app.post("/sessions/{session_id}/abort")
    async def abort_session(session_id: str) -> JSONResponse:
        mission = store.get_mission(session_id)
        if not mission:
            raise HTTPException(status_code=404, detail="Session not found")
        stop_listener_for_mission(
            session_id,
            sub_store=sub_store,
            mission_store=store,
        )
        return JSONResponse(content={"session_id": session_id, "status": "cancelled"})

    @app.delete("/sessions/{session_id}")
    @app.post("/sessions/{session_id}/dismiss")
    async def dismiss_session(session_id: str) -> JSONResponse:
        try:
            store.hide_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(content={"session_id": session_id, "dismissed": True})

    @app.get("/sessions/{session_id}/events")
    async def session_events(session_id: str, request: Request) -> StreamingResponse:
        return await mission_events(session_id, request)

    @app.get("/sessions/{session_id}/history")
    async def session_history(session_id: str) -> JSONResponse:
        mission = store.get_mission(session_id)
        if not mission:
            raise HTTPException(status_code=404, detail="Session not found")
        events = store.list_events(session_id)
        for event in events:
            event.pop("_event_id", None)
        return JSONResponse(
            content={
                "events": events,
                "session": enrich_session_dict(mission, sub_store=sub_store),
            }
        )

    @app.get("/missions")
    async def list_missions() -> JSONResponse:
        missions = [m.to_session_dict() for m in store.list_missions(limit=50)]
        return JSONResponse(content={"missions": missions, "sessions": missions})

    @app.post("/missions")
    async def create_mission(request: Request) -> JSONResponse:
        payload: dict[str, Any] = await request.json()
        instruction = str(payload.get("instruction") or payload.get("text") or "").strip()
        if not instruction:
            raise HTTPException(status_code=400, detail="instruction is required")
        thread_id = str(payload.get("thread_id") or "").strip() or None
        mission = store.create_mission(instruction=instruction, thread_id=thread_id)
        return JSONResponse(
            content={
                "mission_id": mission.id,
                "thread_id": mission.thread_id,
                "status": mission.status.value,
            }
        )

    @app.get("/missions/{mission_id}")
    async def get_mission(mission_id: str) -> JSONResponse:
        mission = store.get_mission(mission_id)
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")
        return JSONResponse(content=mission.to_dict())

    @app.get("/missions/{mission_id}/events")
    async def mission_events(mission_id: str, request: Request) -> StreamingResponse:
        mission = store.get_mission(mission_id)
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")

        after_id = int(request.query_params.get("after", "0") or "0")

        async def replay() -> AsyncIterator[str]:
            nonlocal after_id
            while True:
                events = store.list_events(mission_id, after_id=after_id)
                for event in events:
                    event_id = event.pop("_event_id", None)
                    if event_id:
                        after_id = int(event_id)
                    yield f"data: {json.dumps(event)}\n\n"
                current = store.get_mission(mission_id)
                terminal = current and current.status in {
                    MissionStatus.COMPLETED,
                    MissionStatus.FAILED,
                    MissionStatus.CANCELLED,
                }
                if current and current.session_type == SessionType.RECURRING:
                    terminal = current.status == MissionStatus.CANCELLED
                if terminal:
                    if not events:
                        yield f"data: {json.dumps({'event': 'done', 'thread_id': current.thread_id})}\n\n"
                    break
                await asyncio.sleep(0.5)

        return StreamingResponse(
            replay(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/chat/stream")
    async def chat_stream(request: Request) -> StreamingResponse:
        payload: dict[str, Any] = await request.json()
        text = str(payload.get("text", "")).strip()
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        conversation_id = (
            str(payload.get("conversation_id") or payload.get("thread_id") or "").strip()
            or str(uuid.uuid4())
        )
        conv_store.ensure_conversation(conversation_id, title=text[:80])
        prior_history = conv_store.to_langchain_messages(conversation_id)
        conv_store.append_message(conversation_id, role="user", content=text)
        if len(prior_history) == 0:
            conv_store.touch_conversation(conversation_id, title=text[:80])
        thread_id = conversation_id
        mission = store.create_mission(
            instruction=text,
            thread_id=thread_id,
            conversation_id=conversation_id,
        )
        mission_id = mission.id
        user_id = _user(request)
        current_user_id.set(user_id)
        client_tz = client_timezone_from_request(request, payload)
        if client_tz:
            activate_user_timezone(user_id, from_client=client_tz)

        async def persist(event: dict[str, Any]) -> None:
            store.append_event(mission_id, event)

        async def run_and_mark() -> None:
            final_text: str | None = None
            final_ui: list[dict[str, Any]] | None = None
            had_error = False
            error_message: str | None = None
            store.update_status(mission_id, MissionStatus.RUNNING)
            conv_token = current_conversation_id.set(conversation_id)
            mission_token = current_mission_id.set(mission_id)

            async def persist_with_status(event: dict[str, Any]) -> None:
                nonlocal final_text, final_ui, had_error, error_message
                if event.get("event") == "error":
                    had_error = True
                    error_message = str(event.get("message") or "Session failed")
                if event.get("event") == "final":
                    final_text = event.get("text")
                    final_ui = event.get("ui") or []
                    if final_text:
                        conv_store.append_message(
                            conversation_id,
                            role="assistant",
                            content=str(final_text),
                        )
                await persist(event)

            try:
                async for _line in stream_mission_graph(
                    text,
                    thread_id,
                    history=prior_history,
                    on_event=persist_with_status,
                ):
                    pass
                current = store.get_mission(mission_id) or mission
                finalize_session_status(
                    store,
                    current,
                    had_error=had_error,
                    error_message=error_message,
                    final_text=final_text,
                    final_ui=final_ui,
                )
            except Exception as exc:
                store.update_status(mission_id, MissionStatus.FAILED, error=str(exc))
            finally:
                current_conversation_id.reset(conv_token)
                current_mission_id.reset(mission_token)

        async def stream() -> AsyncIterator[str]:
            created = {
                "event": "session_created",
                "session_id": mission_id,
                "mission_id": mission_id,
                "thread_id": thread_id,
                "conversation_id": conversation_id,
                "session_type": mission.session_type.value,
            }
            yield f"data: {json.dumps(created)}\n\n"
            task = asyncio.create_task(run_and_mark())
            try:
                after_id = 0
                while not task.done():
                    events = store.list_events(mission_id, after_id=after_id)
                    for event in events:
                        eid = event.pop("_event_id", None)
                        if eid:
                            after_id = int(eid)
                        yield f"data: {json.dumps(event)}\n\n"
                    await asyncio.sleep(0.15)
                events = store.list_events(mission_id, after_id=after_id)
                for event in events:
                    event.pop("_event_id", None)
                    yield f"data: {json.dumps(event)}\n\n"
            finally:
                if not task.done():
                    await task

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Session-Id": mission_id,
                "X-Mission-Id": mission_id,
            },
        )

    @app.post("/chat")
    async def chat_message(request: Request) -> JSONResponse:
        payload: dict[str, Any] = await request.json()
        text = str(payload.get("text", "")).strip()
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        thread_id = str(payload.get("thread_id") or "").strip() or str(uuid.uuid4())
        mission = store.create_mission(instruction=text, thread_id=thread_id)
        store.update_status(mission.id, MissionStatus.RUNNING)
        try:
            graph = await ensure_graph()
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=text)]},
                config=_thread_config(thread_id),
            )
            message = result["messages"][-1]
            response_text = (
                message.content if isinstance(message.content, str) else str(message.content)
            )
            ui = _ui_items(result)
            store.update_status(
                mission.id,
                MissionStatus.COMPLETED,
                result_text=response_text,
                result_ui=ui,
            )
            return JSONResponse(
                content={
                    "mission_id": mission.id,
                    "thread_id": thread_id,
                    "text": response_text,
                    "ui": ui,
                    "plan": result.get("plan") or {},
                    "route": result.get("route"),
                    "complexity": result.get("complexity"),
                    "subtask_results": result.get("subtask_results") or [],
                }
            )
        except Exception as exc:
            store.update_status(mission.id, MissionStatus.FAILED, error=str(exc))
            return JSONResponse(
                status_code=500,
                content={"text": str(exc), "error": True, "mission_id": mission.id},
            )

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/chat", status_code=307)

    return app


app = create_app()
