"""Application configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "file:./prisma/dev.db"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"

    heartbeat_timeout_seconds: int = 90
    stale_check_interval_seconds: int = 30
    cors_origins: str = "*"

    def prisma_database_url(self) -> str:
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
