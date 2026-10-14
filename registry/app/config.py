"""Application configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # SQLite path; Prisma-style `file:./...` is accepted and normalized.
    database_url: str = "sqlite+aiosqlite:///./registry.db"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"

    heartbeat_timeout_seconds: int = 90
    stale_check_interval_seconds: int = 30
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
