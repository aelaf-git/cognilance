"""Coordinator server settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return default


@dataclass(frozen=True)
class Settings:
    host: str
    port: int

    @classmethod
    def from_env(cls) -> Settings:
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
        )


def get_settings() -> Settings:
    return Settings.from_env()
