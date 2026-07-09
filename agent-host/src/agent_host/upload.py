"""Safe ZIP upload, extract, and entry detection."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

_WORKER_PATTERN = re.compile(r"\bCognilanceWorker\s*\(")


@dataclass
class UploadResult:
    entry_file: str
    name: str
    has_requirements: bool


class UploadError(Exception):
    pass


def _is_safe_zip_member(name: str) -> bool:
    path = Path(name)
    if path.is_absolute():
        return False
    if ".." in path.parts:
        return False
    return True


def _scan_for_worker(py_path: Path) -> bool:
    try:
        text = py_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return bool(_WORKER_PATTERN.search(text))


def find_worker_entry_files(root: Path) -> list[Path]:
    matches: list[Path] = []
    for py_file in sorted(root.rglob("*.py")):
        if _scan_for_worker(py_file):
            matches.append(py_file.relative_to(root))
    return matches


def _load_manifest(root: Path) -> dict:
    manifest_path = root / "cognilance.json"
    if not manifest_path.is_file():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadError(f"Invalid cognilance.json: {exc}") from exc
    if not isinstance(data, dict):
        raise UploadError("cognilance.json must be a JSON object")
    return data


def detect_entry(root: Path) -> tuple[str, str]:
    """Return (entry_file, display_name)."""
    manifest = _load_manifest(root)
    candidates = find_worker_entry_files(root)
    if not candidates:
        raise UploadError(
            "ZIP must contain at least one .py file defining a CognilanceWorker instance"
        )

    entry = manifest.get("entry")
    if entry:
        entry_path = Path(entry)
        if entry_path not in candidates and not (root / entry_path).is_file():
            raise UploadError(f"cognilance.json entry not found or has no CognilanceWorker: {entry}")
        if not _scan_for_worker(root / entry_path):
            raise UploadError(f"Entry file does not define CognilanceWorker: {entry}")
        chosen = str(entry_path).replace("\\", "/")
    else:
        chosen = str(candidates[0]).replace("\\", "/")

    name = manifest.get("name")
    if not isinstance(name, str) or not name.strip():
        name = Path(chosen).stem.replace("_", " ").title()
    return chosen, name.strip()


def extract_zip(zip_bytes: bytes, dest_dir: Path, *, max_bytes: int) -> UploadResult:
    if len(zip_bytes) > max_bytes:
        raise UploadError(f"ZIP exceeds maximum size of {max_bytes // (1024 * 1024)} MB")

    dest_dir.mkdir(parents=True, exist_ok=True)
    for child in dest_dir.iterdir():
        if child.is_dir():
            for sub in child.rglob("*"):
                if sub.is_file():
                    sub.unlink()
            for sub in sorted(child.rglob("*"), reverse=True):
                if sub.is_dir():
                    sub.rmdir()
            child.rmdir()
        elif child.is_file():
            child.unlink()

    try:
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if not _is_safe_zip_member(info.filename):
                    raise UploadError(f"Unsafe path in ZIP: {info.filename}")
            zf.extractall(dest_dir)
    except zipfile.BadZipFile as exc:
        raise UploadError("Invalid ZIP file") from exc

    # If everything landed in a single top-level folder, use that as root.
    children = [p for p in dest_dir.iterdir() if p.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir():
        inner = children[0]
        for item in inner.iterdir():
            item.rename(dest_dir / item.name)
        inner.rmdir()

    entry_file, name = detect_entry(dest_dir)
    has_requirements = (dest_dir / "requirements.txt").is_file()
    return UploadResult(entry_file=entry_file, name=name, has_requirements=has_requirements)
