"""CLI entry point for the coordinator server."""

from __future__ import annotations

import core.context.env  # noqa: F401

import uvicorn

from core.config import get_settings


def cli() -> None:
    settings = get_settings()
    base = f"http://127.0.0.1:{settings.port}"
    banner = (
        f"Cognilance\n"
        f"  health:  {base}/health\n"
        f"  sessions: {base}/sessions\n"
        f"  agents:   {base}/skills/online\n"
        f"\nRun background worker: cognilance-coordinator-worker\n"
    )
    print(banner, flush=True)
    uvicorn.run(
        "api.server:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    cli()
