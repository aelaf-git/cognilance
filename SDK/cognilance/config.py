"""Configuration and environment loading."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

DEFAULT_REGISTRY_URL = "http://127.0.0.1:8088"
DEFAULT_PORT = 8000
HEARTBEAT_INTERVAL_SECONDS = 30


@dataclass(frozen=True)
class Config:
    registry_url: str
    port: int = DEFAULT_PORT

    @classmethod
    def from_env(cls, *, port: int | None = None) -> Config:
        return cls(
            registry_url=os.getenv("COGNILANCE_REGISTRY_URL", DEFAULT_REGISTRY_URL).rstrip("/"),
            port=port or int(os.getenv("COGNILANCE_PORT", str(DEFAULT_PORT))),
        )
