"""Durable run inspection."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from api.deps import board_store, run_store

router = APIRouter(prefix="/runs")


@router.get("/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    steps = [s.to_dict() for s in run_store.list_steps(run_id)]
    tasks = [t.to_dict() for t in board_store.list_for_run(run_id)]
    return JSONResponse(content={"run": run.to_dict(), "steps": steps, "board_tasks": tasks})
