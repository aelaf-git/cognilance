"""Tool-proxy HTTP routers: credentials never leave the broker."""

from core.broker.proxy.docs import router as docs_router
from core.broker.proxy.gmail import router as gmail_router

__all__ = ["gmail_router", "docs_router"]
