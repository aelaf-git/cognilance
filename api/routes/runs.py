"""Durable run inspection."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from api.deps import board_store, owner_filter, run_store, user_from

router = APIRouter(prefix="/runs")


@router.get("/{run_id}")
async def get_run(run_id: str, request: Request) -> JSONResponse:
    scope = owner_filter(user_from(request))
    run = run_store.get_run(run_id, **scope)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    steps = [s.to_dict() for s in run_store.list_steps(run_id)]
    tasks = [t.to_dict() for t in board_store.list_for_run(run_id, **scope)]
    return JSONResponse(content={"run": run.to_dict(), "steps": steps, "board_tasks": tasks})
