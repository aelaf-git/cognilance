"""Agent Host settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "cognilance").is_dir():
            return parent
    return Path.cwd()


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    data_dir: Path
    db_path: Path
    registry_url: str
    port_range_start: int
    port_range_end: int
    max_zip_bytes: int
    pip_timeout_seconds: int
    health_timeout_seconds: int
    repo_root: Path

    @classmethod
    def from_env(cls) -> Settings:
        root = _repo_root()
        data_dir = Path(
            os.getenv("COGNILANCE_AGENT_HOST_DATA_DIR", str(root / "data" / "hosted-agents"))
        )
        return cls(
            host=os.getenv("COGNILANCE_AGENT_HOST_HOST", "0.0.0.0"),
            port=int(os.getenv("COGNILANCE_AGENT_HOST_PORT", "8300")),
            data_dir=data_dir,
            db_path=data_dir / "agent_host.db",
            registry_url=os.getenv("COGNILANCE_REGISTRY_URL", "http://127.0.0.1:8088"),
            port_range_start=int(os.getenv("COGNILANCE_AGENT_HOST_PORT_START", "8104")),
            port_range_end=int(os.getenv("COGNILANCE_AGENT_HOST_PORT_END", "8199")),
            max_zip_bytes=int(os.getenv("COGNILANCE_AGENT_HOST_MAX_ZIP_MB", "15")) * 1024 * 1024,
            pip_timeout_seconds=int(os.getenv("COGNILANCE_AGENT_HOST_PIP_TIMEOUT", "120")),
            health_timeout_seconds=int(os.getenv("COGNILANCE_AGENT_HOST_HEALTH_TIMEOUT", "30")),
            repo_root=root,
        )


def get_settings() -> Settings:
    return Settings.from_env()
