"""Brand assets shipped with the Cognilance SDK."""

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent
LOGO_PATH = ASSETS_DIR / "logo.png"
INTEGRATIONS_DIR = ASSETS_DIR / "integrations"

# Prefer known extensions per integration id (served at /integrations/logos/{id}).
INTEGRATION_LOGO_FILES: dict[str, str] = {
    "gmail": "gmail.webp",
    "drive": "drive.webp",
    "calendar": "calendar.webp",
    "notion": "notion.png",
    "slack": "slack.webp",
    "github": "github.webp",
}

_MEDIA_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def integration_logo_path(integration_id: str) -> Path | None:
    """Resolve a logo file for an integration id, or None if missing."""
    name = INTEGRATION_LOGO_FILES.get(integration_id)
    if name:
        path = INTEGRATIONS_DIR / name
        if path.is_file():
            return path
    # Fallback: any matching stem in the integrations dir.
    for path in INTEGRATIONS_DIR.glob(f"{integration_id}.*"):
        if path.is_file():
            return path
    return None


def integration_logo_media_type(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


__all__ = [
    "ASSETS_DIR",
    "INTEGRATIONS_DIR",
    "INTEGRATION_LOGO_FILES",
    "LOGO_PATH",
    "integration_logo_media_type",
    "integration_logo_path",
]
