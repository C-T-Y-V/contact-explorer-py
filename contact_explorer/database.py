"""Small SQLite connection wrapper used by the local Python backend."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "contact_explorer.db"


class Database:
    def __init__(self, path: str | Path | None = None) -> None:
        if path:
            self.path = Path(path)
        elif os.getenv("CONTACT_EXPLORER_DB"):
            self.path = Path(os.environ["CONTACT_EXPLORER_DB"])
        else:
            self.path = DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=15,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 15000")
        self.initialise()

    def initialise(self) -> None:
        with self.lock:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    company TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    photo_uri TEXT,
                    is_favorite INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    times_contacted INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS contact_phones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    label TEXT NOT NULL DEFAULT 'Mobile',
                    number TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS contact_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    label TEXT NOT NULL DEFAULT 'Home',
                    email TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS folders (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE,
                    parent_folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS contact_groups (
                    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    group_id TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                    PRIMARY KEY (contact_id, group_id)
                );
                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE
                );
                CREATE TABLE IF NOT EXISTS contact_tags (
                    contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY (contact_id, tag_id)
                );
                CREATE TABLE IF NOT EXISTS recent_contacts (
                    contact_id TEXT PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
                    viewed_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS deleted_contacts (
                    contact_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    deleted_at INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS contact_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_id TEXT,
                    contact_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    occurred_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS smart_groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    field TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name COLLATE NOCASE);
                CREATE INDEX IF NOT EXISTS idx_phones_contact ON contact_phones(contact_id);
                CREATE INDEX IF NOT EXISTS idx_phones_number ON contact_phones(number);
                CREATE INDEX IF NOT EXISTS idx_emails_contact ON contact_emails(contact_id);
                CREATE INDEX IF NOT EXISTS idx_groups_parent ON folders(parent_folder_id);
                CREATE INDEX IF NOT EXISTS idx_memberships_group ON contact_groups(group_id);
                CREATE INDEX IF NOT EXISTS idx_tags_contact ON contact_tags(contact_id);
                CREATE INDEX IF NOT EXISTS idx_events_time ON contact_events(occurred_at DESC);
                """
            )
            self.connection.commit()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            try:
                yield self.connection
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def close(self) -> None:
        with self.lock:
            self.connection.close()
