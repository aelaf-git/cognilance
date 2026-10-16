"""Durable LangGraph pipelines. Each folder exposes ``graph.py`` with ``ensure_graph``."""

from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path
from types import ModuleType

PIPELINES_DIR = Path(__file__).resolve().parent
DEFAULT_PIPELINE = "coordinator_board"


def available_pipelines() -> list[str]:
    return sorted(
        p.parent.name
        for p in PIPELINES_DIR.glob("*/graph.py")
        if p.parent.name != "shared"
    )


@lru_cache(maxsize=None)
def get_pipeline(name: str | None = None) -> ModuleType:
    """Import ``pipelines.<name>.graph`` (defaults to the coordinator board)."""
    target = (name or DEFAULT_PIPELINE).strip()
    if target not in available_pipelines():
        raise KeyError(f"Unknown pipeline: {target}")
    return importlib.import_module(f"pipelines.{target}.graph")


__all__ = ["DEFAULT_PIPELINE", "PIPELINES_DIR", "available_pipelines", "get_pipeline"]
