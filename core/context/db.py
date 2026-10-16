"""SQLite database path for coordinator persistence."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DIR = REPO_ROOT / "data"
_default_path = _DEFAULT_DIR / "coordinator.db"
# Prefer new env; fall back to legacy env/path for existing installs.
_env_path = os.getenv("COGNILANCE_COORDINATOR_DB") or os.getenv("COGNILANCE_ORCHESTRATOR_DB")
if not _env_path:
    legacy = _DEFAULT_DIR / "orchestrator.db"
    if legacy.exists() and not _default_path.exists():
        _env_path = str(legacy)
DB_PATH = Path(_env_path or str(_default_path))


def ensure_db_dir() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH
