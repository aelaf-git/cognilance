from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from prisma import Prisma

from app.database import get_db
from app.schemas import StatusResponse, TraceDetailResponse, TraceEventIn, TraceListResponse
from app.services import traces as trace_service
from app.ws import TraceHub

router = APIRouter(prefix="/v1/traces", tags=["traces"])


def get_hub(request: Request) -> TraceHub:
    return request.app.state.trace_hub


@router.post("/events", response_model=StatusResponse)
async def collect_event(
    body: TraceEventIn,
    db: Prisma = Depends(get_db),
    hub: TraceHub = Depends(get_hub),
) -> StatusResponse:
    payload = await trace_service.ingest_event(db, body=body)
    await hub.broadcast({"kind": "event", "event": payload})
    return StatusResponse()


@router.get("", response_model=TraceListResponse)
async def list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    db: Prisma = Depends(get_db),
) -> TraceListResponse:
    traces = await trace_service.list_traces(db, limit=limit)
    return TraceListResponse(traces=traces)


@router.get("/{trace_id}", response_model=TraceDetailResponse)
async def get_trace(
    trace_id: str,
    db: Prisma = Depends(get_db),
) -> TraceDetailResponse:
    try:
        events = await trace_service.get_trace(db, trace_id=trace_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Trace not found") from exc
    return TraceDetailResponse(trace_id=trace_id, events=events)


@router.websocket("/ws")
async def trace_ws(websocket: WebSocket) -> None:
    hub: TraceHub = websocket.app.state.trace_hub
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(websocket)
