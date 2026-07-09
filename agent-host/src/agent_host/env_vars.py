"""Validation helpers for per-agent environment variables."""

from __future__ import annotations

import re

_ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_MAX_VARS = 50
_MAX_KEY_LEN = 128
_MAX_VALUE_LEN = 8192

# Host injects these at start — developers cannot override via stored secrets.
_RESERVED_KEYS = frozenset({"COGNILANCE_PORT", "COGNILANCE_REGISTRY_URL"})


class EnvValidationError(ValueError):
    pass


def validate_env_key(key: str) -> str:
    normalized = key.strip().upper()
    if not normalized:
        raise EnvValidationError("Environment variable names cannot be empty")
    if len(normalized) > _MAX_KEY_LEN:
        raise EnvValidationError(f"Key too long: {normalized[:32]}…")
    if not _ENV_KEY_RE.match(normalized):
        raise EnvValidationError(
            f"Invalid key {normalized!r} — use UPPER_SNAKE_CASE (e.g. GROQ_API_KEY)"
        )
    if normalized in _RESERVED_KEYS:
        raise EnvValidationError(f"{normalized} is managed by the Agent Host and cannot be set")
    return normalized


def normalize_env(env: dict[str, str]) -> dict[str, str]:
    if not env:
        return {}
    if len(env) > _MAX_VARS:
        raise EnvValidationError(f"At most {_MAX_VARS} environment variables allowed")

    normalized: dict[str, str] = {}
    for raw_key, raw_value in env.items():
        key = validate_env_key(raw_key)
        if key in normalized:
            raise EnvValidationError(f"Duplicate key: {key}")
        if not isinstance(raw_value, str):
            raise EnvValidationError(f"Value for {key} must be a string")
        if len(raw_value) > _MAX_VALUE_LEN:
            raise EnvValidationError(f"Value for {key} exceeds maximum length")
        normalized[key] = raw_value
    return normalized
