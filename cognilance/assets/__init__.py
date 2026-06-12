"""Brand assets shipped with the Cognilance SDK."""

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent
LOGO_PATH = ASSETS_DIR / "logo.png"

__all__ = ["ASSETS_DIR", "LOGO_PATH"]
