"""FastAPI server for the orchestrator chat UI."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from cognilance.assets import LOGO_PATH
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from langchain_core.messages import HumanMessage

from orchestrator.graph import graph
from orchestrator.ui.chat import orchestrator_chat_html


def _ui_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": item["name"], "props": item.get("props") or {}}
        for item in (result.get("ui") or [])
        if item.get("type") == "ui"
    ]


def _meta_from_result(result: dict[str, Any], message: Any) -> str | None:
    plan = result.get("plan") or {}
    hire = result.get("hire_result") or {}
    meta_parts: list[str] = []
    if plan.get("reasoning"):
        meta_parts.append(f"plan: {plan['reasoning']}")
    if hire.get("agent_name"):
        meta_parts.append(f"hired: {hire['agent_name']}")
    elif hire.get("mode") == "general":
        meta_parts.append("mode: general")
    extra = (message.additional_kwargs or {}).get("orchestrator_meta")
    if extra:
        meta_parts.append(str(extra))
    return " · ".join(meta_parts) if meta_parts else None


def _normalize_custom_event(chunk: dict[str, Any]) -> dict[str, Any] | None:
    if chunk.get("event"):
        return chunk
    if chunk.get("type") == "ui":
        return {
            "event": "ui",
            "name": chunk.get("name"),
            "props": chunk.get("props") or {},
        }
    return None


async def _stream_chat(text: str) -> AsyncIterator[str]:
    final: dict[str, Any] | None = None
    try:
        async for mode, chunk in graph.astream(
            {"messages": [HumanMessage(content=text)]},
            stream_mode=["custom", "values"],
        ):
            if mode == "custom" and isinstance(chunk, dict):
                event = _normalize_custom_event(chunk)
                if event:
                    yield f"data: {json.dumps(event)}\n\n"
            elif mode == "values":
                final = chunk
    except Exception as exc:
        yield f"data: {json.dumps({'event': 'error', 'message': str(exc)})}\n\n"
        return

    if final and final.get("messages"):
        message = final["messages"][-1]
        payload = {
            "event": "final",
            "text": message.content
            if isinstance(message.content, str)
            else str(message.content),
            "ui": _ui_items(final),
            "plan": final.get("plan") or {},
            "meta": _meta_from_result(final, message),
        }
        yield f"data: {json.dumps(payload)}\n\n"

    yield f"data: {json.dumps({'event': 'done'})}\n\n"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cognilance Orchestrator",
        description="LangGraph planner + generative UI for the agent marketplace",
        version="0.1.0",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/logo.png")
    async def logo() -> FileResponse:
        if not LOGO_PATH.is_file():
            raise HTTPException(status_code=404, detail="Logo not found")
        return FileResponse(LOGO_PATH, media_type="image/png")

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page() -> str:
        return orchestrator_chat_html()

    @app.post("/chat/stream")
    async def chat_stream(request: Request) -> StreamingResponse:
        payload: dict[str, Any] = await request.json()
        text = str(payload.get("text", "")).strip()
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        return StreamingResponse(
            _stream_chat(text),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/chat")
    async def chat_message(request: Request) -> JSONResponse:
        payload: dict[str, Any] = await request.json()
        text = str(payload.get("text", "")).strip()
        if not text:
            raise HTTPException(status_code=400, detail="text is required")
        try:
            result = await graph.ainvoke({"messages": [HumanMessage(content=text)]})
            message = result["messages"][-1]
            return JSONResponse(
                content={
                    "text": message.content
                    if isinstance(message.content, str)
                    else str(message.content),
                    "ui": _ui_items(result),
                    "plan": result.get("plan") or {},
                    "meta": _meta_from_result(result, message),
                }
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"text": str(exc), "error": True},
            )

    @app.get("/")
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/chat", status_code=307)

    return app


app = create_app()
