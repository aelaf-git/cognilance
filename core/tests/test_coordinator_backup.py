"""Copied coordinator and checkpoint files restore the same rows."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from core.context.conversations.store import ConversationStore
from core.runtime.checkpointer import checkpoint_db_path
from core.runtime.runs.store import RunStore

ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = ROOT / "scripts" / "backup_coordinator.py"


def _backup():
    spec = importlib.util.spec_from_file_location("backup_coordinator", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restore_brings_conversation_run_and_checkpoint_back(tmp_path: Path):
    source = tmp_path / "data"
    saved = tmp_path / "backups"
    source.mkdir()
    db = source / "coordinator.db"
    conversations = ConversationStore(str(db))
    runs = RunStore(str(db))
    conversations.init_db()
    runs.init_db()
    conversation = conversations.create_conversation(title="Launch thread")
    run = runs.create_run(
        instruction="Write the weekly report",
        thread_id="thread-1",
        conversation_id=conversation.id,
        run_id="run-1",
    )
    checkpoints = sqlite3.connect(source / "checkpoints.db")
    try:
        checkpoints.execute(
            "CREATE TABLE checkpoints (thread_id TEXT PRIMARY KEY, checkpoint TEXT NOT NULL)"
        )
        checkpoints.execute(
            "INSERT INTO checkpoints (thread_id, checkpoint) VALUES (?, ?)",
            ("thread-1", "saved"),
        )
        checkpoints.commit()
    finally:
        checkpoints.close()

    backup = _backup()
    backup.copy_databases(source, saved)
    db.unlink()
    (source / "checkpoints.db").unlink()

    backup.restore_databases(saved, source)

    restored_conversation = ConversationStore(str(db)).get_conversation(conversation.id)
    restored_run = RunStore(str(db)).get_run(run.id)
    assert restored_conversation is not None
    assert restored_conversation.title == "Launch thread"
    assert restored_run is not None
    assert restored_run.instruction == "Write the weekly report"
    assert restored_run.conversation_id == conversation.id
    with sqlite3.connect(source / "checkpoints.db") as conn:
        row = conn.execute(
            "SELECT checkpoint FROM checkpoints WHERE thread_id = ?",
            ("thread-1",),
        ).fetchone()
    assert row is not None
    assert row[0] == "saved"


def test_compose_volume_keeps_both_sqlite_files(monkeypatch: pytest.MonkeyPatch):
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "coordinator_data:/data" in text
    assert "COGNILANCE_COORDINATOR_DB: /data/coordinator.db" in text
    monkeypatch.setenv("COGNILANCE_COORDINATOR_DB", "/data/coordinator.db")
    assert Path(checkpoint_db_path()) == Path("/data/checkpoints.db")
