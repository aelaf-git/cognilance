"""CLI entry point for the orchestrator server."""

from __future__ import annotations

import orchestrator.env  # noqa: F401

import uvicorn

from orchestrator.config import get_settings


def cli() -> None:
    settings = get_settings()
    base = f"http://127.0.0.1:{settings.port}"
    banner = (
        f"Cognilance Orchestrator Agent\n"
        f"  chat UI: {base}/chat\n"
        f"  health:  {base}/health\n"
        f"  missions: {base}/missions\n"
        f"  apps:     {base}/apps\n"
        f"\nRun background worker: cognilance-orchestrator-worker\n"
    )
    print(banner, flush=True)
    uvicorn.run(
        "orchestrator.server:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    cli()
