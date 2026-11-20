"""Coordinator server settings."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB_DIR = REPO_ROOT / "data"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "coordinator.db"
_DEMO_SESSION_SECRET = b"cognilance-dev-insecure-session"
_DEMO_TOOL_PROXY_KEY = b"cognilance-dev-insecure-tool-proxy"


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return default


def _demo_mode_from_env() -> bool:
    return _env("COGNILANCE_DEMO").strip().lower() in {"1", "true", "yes"}


def _coordinator_db_from_env() -> Path:
    explicit = _env("COGNILANCE_COORDINATOR_DB", "COGNILANCE_ORCHESTRATOR_DB")
    if explicit:
        return Path(explicit)
    legacy = _DEFAULT_DB_DIR / "orchestrator.db"
    if legacy.exists() and not _DEFAULT_DB_PATH.exists():
        return legacy
    return _DEFAULT_DB_PATH


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    demo_mode: bool
    session_secret: str | None
    tool_proxy_signing_key: str | None
    gemini_api_key: str
    approval_grades: str
    coordinator_db: Path
    github_client_id: str
    github_client_secret: str

    @classmethod
    def from_env(cls) -> Settings:
        session = _env("COORDINATOR_SESSION_SECRET", "ORCHESTRATOR_SESSION_SECRET")
        tool_key = _env("TOOL_PROXY_SIGNING_KEY")
        return cls(
            host=_env(
                "COGNILANCE_COORDINATOR_HOST",
                "COGNILANCE_ORCHESTRATOR_HOST",
                default="0.0.0.0",
            ),
            port=int(
                _env(
                    "COGNILANCE_COORDINATOR_PORT",
                    "COGNILANCE_ORCHESTRATOR_PORT",
                    default="8200",
                )
            ),
            demo_mode=_demo_mode_from_env(),
            session_secret=session or None,
            tool_proxy_signing_key=tool_key or None,
            gemini_api_key=_env("GEMINI_API_KEY", "GOOGLE_API_KEY").strip(),
            approval_grades=_env("COGNILANCE_APPROVAL_GRADES", default="irreversible"),
            coordinator_db=_coordinator_db_from_env(),
            github_client_id=_env("GITHUB_CLIENT_ID").strip(),
            github_client_secret=_env("GITHUB_CLIENT_SECRET").strip(),
        )


def get_settings() -> Settings:
    return Settings.from_env()


def session_secret_bytes(settings: Settings | None = None) -> bytes:
    cfg = settings or get_settings()
    if cfg.session_secret:
        return cfg.session_secret.encode()
    if cfg.demo_mode:
        _log.warning(
            "COORDINATOR_SESSION_SECRET unset; using insecure demo default "
            "(COGNILANCE_DEMO=1)"
        )
        return _DEMO_SESSION_SECRET
    raise RuntimeError(
        "COORDINATOR_SESSION_SECRET is required (or set COGNILANCE_DEMO=1 for local demo)"
    )


def tool_proxy_signing_key_bytes(settings: Settings | None = None) -> bytes:
    cfg = settings or get_settings()
    if cfg.tool_proxy_signing_key:
        return cfg.tool_proxy_signing_key.encode()
    if cfg.demo_mode:
        _log.warning(
            "TOOL_PROXY_SIGNING_KEY unset; using insecure demo default (COGNILANCE_DEMO=1)"
        )
        return _DEMO_TOOL_PROXY_KEY
    raise RuntimeError(
        "TOOL_PROXY_SIGNING_KEY is required (or set COGNILANCE_DEMO=1 for local demo)"
    )
