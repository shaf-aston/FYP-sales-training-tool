"""The accounts database: one SQLite file, a short connection per use, and schema migrations.

A migration is appended to MIGRATIONS and never edited once shipped: the file's `user_version` says how many
have run, so a server picks up new ones on start. WAL mode lets the server's threads read while one writes.
`secure_delete` overwrites deleted rows, so a deleted account's text does not linger in the file.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
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
        session_version INTEGER NOT NULL DEFAULT 1,
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
        role TEXT NOT NULL CHECK (role IN ('member', 'manager')),
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

    @contextmanager
    def connect(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        """A connection for one unit of work: committed when the block ends, rolled back if it raises.
        `write=True` takes the write lock up front (BEGIN IMMEDIATE), so a check-then-insert in the block
        cannot race another request's insert."""
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA secure_delete = ON")
        try:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        finally:
            conn.close()

    def migrate(self) -> int:
        """Run the migrations this file has not had yet, under the write lock (safe if two processes start at
        once: the second sees the first's version). Returns the schema version now."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("BEGIN IMMEDIATE")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
                for statement in (s.strip() for s in script.split(";")):
                    if statement:
                        conn.execute(statement)
                conn.execute(f"PRAGMA user_version = {number}")
            conn.execute("COMMIT")
            return conn.execute("PRAGMA user_version").fetchone()[0]
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def checkpoint(self) -> None:
        """Fold the write-ahead log into the main file and empty it (after a delete, so no copy lingers there)."""
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()


_database: Database | None = None
_database_lock = threading.Lock()


def database() -> Database:
    """The app's database (DB_PATH, relative to the project root), migrated once, on first use by any thread."""
    global _database
    with _database_lock:
        if _database is None:
            path = Path(env_str("DB_PATH", DEFAULT_DB_PATH))
            db = Database(path if path.is_absolute() else ROOT_DIR / path)
            db.migrate()
            _database = db
        return _database


def reset_database() -> None:
    """Forget the open database, so the next use opens DB_PATH again (tests point each one at a new file)."""
    global _database
    with _database_lock:
        _database = None
