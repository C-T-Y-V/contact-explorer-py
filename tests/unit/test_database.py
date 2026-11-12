"""Unit tests for Contact Explorer SQLite database engine."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from contact_explorer.database import Database


def test_database_initialization_and_pragmas(temp_db_path: Path) -> None:
    db = Database(temp_db_path)
    try:
        # Check foreign keys pragma
        row = db.connection.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1

        # Check tables creation
        tables = [
            r[0]
            for r in db.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        assert "contacts" in tables
        assert "contact_phones" in tables
        assert "contact_emails" in tables
        assert "folders" in tables
        assert "tags" in tables
        assert "deleted_contacts" in tables
        assert "contact_events" in tables
    finally:
        db.close()


def test_transaction_commit_and_rollback(temp_db_path: Path) -> None:
    db = Database(temp_db_path)
    try:
        # Successful transaction
        with db.transaction():
            db.connection.execute(
                "INSERT INTO tags (id, name) VALUES (?, ?)", ("t-1", "test-tag")
            )

        row = db.connection.execute("SELECT name FROM tags WHERE id='t-1'").fetchone()
        assert row["name"] == "test-tag"

        # Failed transaction should roll back
        with pytest.raises(ValueError):
            with db.transaction():
                db.connection.execute(
                    "INSERT INTO tags (id, name) VALUES (?, ?)", ("t-2", "rollback-tag")
                )
                raise ValueError("Simulated operational failure")

        row_rollback = db.connection.execute("SELECT name FROM tags WHERE id='t-2'").fetchone()
        assert row_rollback is None
    finally:
        db.close()


def test_thread_safety_with_rlock(temp_db_path: Path) -> None:
    db = Database(temp_db_path)
    errors: list[Exception] = []

    def worker(worker_id: int) -> None:
        try:
            for i in range(10):
                with db.transaction():
                    tag_id = f"t-{worker_id}-{i}"
                    db.connection.execute(
                        "INSERT INTO tags (id, name) VALUES (?, ?)",
                        (tag_id, f"Tag {worker_id}-{i}"),
                    )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent database worker failed: {errors}"
    count = db.connection.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    assert count == 40
    db.close()
