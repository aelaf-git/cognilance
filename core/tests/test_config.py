"""Coordinator settings: fail-closed secrets, env overrides, health smoke."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import health
from core.broker.policy import RiskGrade, _env_grades_requiring_approval
from core.config import (
    get_settings,
    session_secret_bytes,
    tool_proxy_signing_key_bytes,
)


def _clear_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "COORDINATOR_SESSION_SECRET",
        "ORCHESTRATOR_SESSION_SECRET",
        "TOOL_PROXY_SIGNING_KEY",
        "COGNILANCE_DEMO",
    ):
        monkeypatch.delenv(name, raising=False)


def test_session_secret_fails_closed_outside_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_secrets(monkeypatch)
    with pytest.raises(RuntimeError, match="COORDINATOR_SESSION_SECRET"):
        session_secret_bytes()


def test_session_secret_demo_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_secrets(monkeypatch)
    monkeypatch.setenv("COGNILANCE_DEMO", "1")
    assert session_secret_bytes() == b"cognilance-dev-insecure-session"


def test_tool_proxy_signing_key_fails_closed_outside_demo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_secrets(monkeypatch)
    with pytest.raises(RuntimeError, match="TOOL_PROXY_SIGNING_KEY"):
        tool_proxy_signing_key_bytes()


def test_approval_grades_and_db_path_from_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db = tmp_path / "custom.db"
    monkeypatch.setenv("COGNILANCE_APPROVAL_GRADES", "irreversible,draft")
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", str(db))
    settings = get_settings()
    assert settings.approval_grades == "irreversible,draft"
    assert settings.coordinator_db == db
    assert _env_grades_requiring_approval() == {
        RiskGrade.IRREVERSIBLE,
        RiskGrade.DRAFT,
    }


def test_health_returns_ok() -> None:
    app = FastAPI()
    app.include_router(health.router)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
