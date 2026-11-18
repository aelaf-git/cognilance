"""SQLite database path for coordinator persistence."""

from __future__ import annotations

from pathlib import Path

from core.config import get_settings

DB_PATH: Path = get_settings().coordinator_db


def ensure_db_dir() -> Path:
    path = get_settings().coordinator_db
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep module-level DB_PATH in sync when tests override env between imports.
    global DB_PATH
    DB_PATH = path
    return path
