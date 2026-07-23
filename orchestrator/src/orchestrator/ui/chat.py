"""Built-in orchestrator chat UI — serves the React bundle from static/."""

from __future__ import annotations

from pathlib import Path

_STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"

_FALLBACK = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Cognilance Orchestrator</title></head>
<body style="background:#0e0918;color:#fff;font-family:'IBM Plex Sans',system-ui,sans-serif;padding:2rem">
  <h1>Chat UI not built</h1>
  <p>Run <code>cd orchestrator/chat-ui && npm install && npm run build</code></p>
</body>
</html>"""


def orchestrator_chat_html() -> str:
    if _STATIC_INDEX.is_file():
        return _STATIC_INDEX.read_text(encoding="utf-8")
    return _FALLBACK
