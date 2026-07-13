"""Developer portal HTML bundle."""

from __future__ import annotations

from pathlib import Path

_STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"

_FALLBACK = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Cognilance Agent Host</title></head>
<body style="background:#0a0a0a;color:#fff;font-family:system-ui;padding:2rem">
  <h1>Developer portal not built</h1>
  <p>Run <code>cd agent-host/developer-ui && npm install && npm run build</code></p>
</body>
</html>"""


def developer_portal_html() -> str:
    if _STATIC_INDEX.is_file():
        return _STATIC_INDEX.read_text(encoding="utf-8")
    return _FALLBACK
