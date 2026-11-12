"""Nightly copies of the accounts database, so a broken disk or a bad migration loses at most a day.

`backup()` uses SQLite's online backup: a consistent copy while the server keeps reading and writing (WAL mode). Each
copy is named by date (eloquence-2026-11-12.db), so a second run on the same day replaces that day's copy. Only the
newest `keep` copies stay: a deleted account is gone from the backups too after `keep` days.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path

_NAME = re.compile(r"^(?P<stem>.+)-\d{4}-\d{2}-\d{2}\.db$")


def _copies(dest: Path, stem: str) -> list[Path]:
    """This database's dated copies in `dest`, oldest first (the date in the name sorts as text)."""
    return sorted(p for p in dest.glob(f"{stem}-*.db") if (m := _NAME.match(p.name)) and m["stem"] == stem)


def backup(db_path: Path, dest: Path, keep: int, today: date | None = None) -> Path:
    """Copy the database to `dest`, check the copy reads, and remove all but the newest `keep` copies.
    Returns the new copy. Raises if the database is missing or the copy is damaged (the old copies are kept then)."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    if not db_path.is_file():
        raise FileNotFoundError(f"no database at {db_path}")
    dest.mkdir(mode=0o700, parents=True, exist_ok=True)
    out = dest / f"{db_path.stem}-{(today or date.today()).isoformat()}.db"
    part = out.with_name(out.name + ".part")
    part.unlink(missing_ok=True)
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    try:
        copy = sqlite3.connect(part)
        try:
            src.backup(copy)
            copy.execute("PRAGMA journal_mode = DELETE")   # one self-contained file, no -wal beside it
            if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("the copy failed its integrity check")
        finally:
            copy.close()
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    finally:
        src.close()
    part.chmod(0o600)   # the copy holds the same accounts as the database
    part.replace(out)
    for old in _copies(dest, db_path.stem)[:-keep]:
        old.unlink()
    return out


def restore(copy: Path, db_path: Path) -> None:
    """Put a backup copy in place of the database (the server must be stopped). The old file is kept as .before."""
    if not copy.is_file():
        raise FileNotFoundError(f"no backup at {copy}")
    conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise sqlite3.DatabaseError(f"{copy} failed its integrity check")
    finally:
        conn.close()
    if db_path.exists():
        db_path.replace(db_path.with_name(db_path.name + ".before"))
    for side in ("-wal", "-shm"):   # left from the old database, they would be replayed onto the copy
        db_path.with_name(db_path.name + side).unlink(missing_ok=True)
    db_path.write_bytes(copy.read_bytes())
    db_path.chmod(0o600)
