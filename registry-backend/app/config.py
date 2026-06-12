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
    bootstrap_api_keys: str = ""
    cors_origins: str = "*"

    def prisma_database_url(self) -> str:
        """Normalize DATABASE_URL for Prisma (sqlite file: or postgresql://)."""
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
