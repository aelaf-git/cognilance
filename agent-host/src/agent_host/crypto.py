"""Encrypt hosted-agent environment values at rest."""

from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    raw = (
        os.getenv("AGENT_HOST_ENCRYPTION_KEY", "").strip()
        or os.getenv("INTEGRATION_ENCRYPTION_KEY", "").strip()
        or os.getenv("ORCHESTRATOR_SESSION_SECRET", "").strip()
        or "cognilance-dev-insecure-key"
    )
    return Fernet(_derive_key(raw))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Failed to decrypt agent environment secret") from exc
