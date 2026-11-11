"""The accounts database: one SQLite file, a short connection per use, and schema migrations.

A migration is appended to MIGRATIONS and never edited once shipped: the file's `user_version` says how many
have run, so a server picks up new ones on start. WAL mode lets the server's threads read while one writes.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from core.infra.constants import DEFAULT_DB_PATH
from core.infra.env import ROOT_DIR, env_str

MIGRATIONS: tuple[str, ...] = (
    # 1: users, teams, memberships, skill history, saved prospects
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at INTEGER NOT NULL
    );
    CREATE TABLE teams (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        invite_code TEXT NOT NULL UNIQUE,
        created_at INTEGER NOT NULL
    );
    CREATE TABLE memberships (
        user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('rep', 'manager')),
        joined_at INTEGER NOT NULL
    );
    CREATE TABLE skill_entries (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        session_id TEXT NOT NULL,
        at INTEGER NOT NULL,
        overall INTEGER NOT NULL,
        scores TEXT NOT NULL,
        PRIMARY KEY (user_id, session_id)
    );
    CREATE TABLE prospects (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        profile TEXT NOT NULL,
        created_at INTEGER NOT NULL
    );
    CREATE INDEX skill_entries_by_user ON skill_entries (user_id, at);
    CREATE INDEX prospects_by_user ON prospects (user_id, created_at);
    """,
)


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._migrate_lock = threading.Lock()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """A connection for one unit of work: committed when the block ends, rolled back if it raises."""
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def migrate(self) -> int:
        """Run the migrations this file has not had yet. Returns the schema version now."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._migrate_lock, self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
                conn.executescript(f"BEGIN; {script}; PRAGMA user_version = {number}; COMMIT;")
            return conn.execute("PRAGMA user_version").fetchone()[0]


@lru_cache(maxsize=1)
def database() -> Database:
    """The app's database (DB_PATH, relative to the project root), migrated on first use."""
    path = Path(env_str("DB_PATH", DEFAULT_DB_PATH))
    db = Database(path if path.is_absolute() else ROOT_DIR / path)
    db.migrate()
    return db
