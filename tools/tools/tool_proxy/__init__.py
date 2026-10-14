"""Tool proxy for skill agents via tool-proxy grants."""

from tools.tool_proxy.docs import router as docs_router
from tools.tool_proxy.gmail import router as gmail_router

__all__ = ["gmail_router", "docs_router"]
