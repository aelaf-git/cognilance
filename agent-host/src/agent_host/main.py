"""CLI entry point for the Agent Host server."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from agent_host.config import get_settings


def cli() -> None:
    settings = get_settings()
    load_dotenv(settings.repo_root / ".env")
    base = f"http://127.0.0.1:{settings.port}"
    banner = (
        f"Cognilance Agent Host\n"
        f"  developer portal: {base}/\n"
        f"  health:           {base}/health\n"
        f"  registry:         {settings.registry_url}\n"
        f"  data dir:         {settings.data_dir}\n"
    )
    print(banner, flush=True)
    uvicorn.run(
        "agent_host.server:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    cli()
