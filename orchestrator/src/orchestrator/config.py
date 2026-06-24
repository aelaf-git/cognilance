"""Orchestrator server settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=os.getenv("COGNILANCE_ORCHESTRATOR_HOST", "0.0.0.0"),
            port=int(os.getenv("COGNILANCE_ORCHESTRATOR_PORT", "8200")),
        )


def get_settings() -> Settings:
    return Settings.from_env()
