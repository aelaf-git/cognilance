"""Helpers for running a local registry during development."""

from __future__ import annotations

import threading
import time
from urllib.parse import urlparse

import httpx
import uvicorn

from cognilance.config import DEFAULT_REGISTRY_PORT
from cognilance.registry.server import create_registry_app


def is_local_registry(url: str) -> bool:
    host = urlparse(url).hostname
    return host in {"127.0.0.1", "localhost", "::1"}


def registry_port(url: str) -> int:
    parsed = urlparse(url)
    return parsed.port or DEFAULT_REGISTRY_PORT


def is_registry_reachable(url: str, *, timeout: float = 1.0) -> bool:
    try:
        response = httpx.get(f"{url.rstrip('/')}/health", timeout=timeout)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def ensure_local_registry(url: str) -> None:
    """Start a local registry in the background if the URL is local and unreachable."""
    if not is_local_registry(url) or is_registry_reachable(url):
        return

    host = urlparse(url).hostname or "127.0.0.1"
    port = registry_port(url)
    app = create_registry_app()

    thread = threading.Thread(
        target=lambda: uvicorn.run(app, host=host, port=port, log_level="warning"),
        daemon=True,
        name="cognilance-registry",
    )
    thread.start()

    deadline = time.time() + 5
    while time.time() < deadline:
        if is_registry_reachable(url, timeout=0.5):
            return
        time.sleep(0.1)

    raise RuntimeError(f"Failed to start local registry at {url}")
