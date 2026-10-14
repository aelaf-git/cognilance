"""SQLite database path for orchestrator persistence."""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data"
DB_PATH = Path(os.getenv("COGNILANCE_ORCHESTRATOR_DB", str(_DEFAULT_DIR / "orchestrator.db")))


def ensure_db_dir() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH
