"""Nightly database backups: a consistent copy, rotation to the newest few, and a restore that works."""

import os
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from core.accounts.backup import backup, restore
from core.accounts.db import Database

ROOT = Path(__file__).resolve().parents[1]


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "live" / "eloquence.db"
    Database(path).migrate()
    with Database(path).connect(write=True) as conn:
        conn.execute("INSERT INTO users (email, name, password_hash, created_at) VALUES ('a@x.io', 'A', 'h', 1)")
    return path


def _emails(path: Path) -> list[str]:
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT email FROM users ORDER BY id")]
    finally:
        conn.close()


def test_copy_holds_the_data_and_is_one_private_file(tmp_path):
    db = _db(tmp_path)
    out = backup(db, tmp_path / "backups", keep=7, today=date(2026, 11, 12))
    assert out.name == "eloquence-2026-11-12.db"
    assert _emails(out) == ["a@x.io"]
    assert not out.with_name(out.name + "-wal").exists()
    assert oct(out.stat().st_mode & 0o777) == "0o600"
    assert list((tmp_path / "backups").glob("*.part")) == []


def test_the_database_file_is_private(tmp_path):
    db = _db(tmp_path)
    db.chmod(0o644)   # as an older server left it
    Database(db).migrate()
    assert oct(db.stat().st_mode & 0o777) == "0o600"


def test_copy_includes_writes_still_in_the_wal(tmp_path):
    db = _db(tmp_path)
    open_conn = sqlite3.connect(db)   # an open writer keeps the change in the -wal, not the main file
    open_conn.execute("INSERT INTO users (email, name, password_hash, created_at) VALUES ('b@x.io', 'B', 'h', 2)")
    open_conn.commit()
    try:
        out = backup(db, tmp_path / "backups", keep=7)
    finally:
        open_conn.close()
    assert _emails(out) == ["a@x.io", "b@x.io"]


def test_keeps_only_the_newest_copies(tmp_path):
    db = _db(tmp_path)
    dest = tmp_path / "backups"
    dest.mkdir()
    (dest / "other-2026-01-01.db").write_text("not ours")   # another database's copy is left alone
    for day in range(1, 11):
        backup(db, dest, keep=3, today=date(2026, 11, day))
    assert sorted(p.name for p in dest.iterdir()) == [
        "eloquence-2026-11-08.db", "eloquence-2026-11-09.db", "eloquence-2026-11-10.db", "other-2026-01-01.db"]


def test_same_day_replaces_that_days_copy(tmp_path):
    db = _db(tmp_path)
    dest = tmp_path / "backups"
    backup(db, dest, keep=7, today=date(2026, 11, 12))
    with Database(db).connect(write=True) as conn:
        conn.execute("DELETE FROM users")
    backup(db, dest, keep=7, today=date(2026, 11, 12))
    assert [p.name for p in dest.iterdir()] == ["eloquence-2026-11-12.db"]
    assert _emails(dest / "eloquence-2026-11-12.db") == []


def test_missing_database_or_bad_keep_fails_and_keeps_old_copies(tmp_path):
    db = _db(tmp_path)
    dest = tmp_path / "backups"
    first = backup(db, dest, keep=2, today=date(2026, 11, 1))
    with pytest.raises(FileNotFoundError):
        backup(tmp_path / "nope.db", dest, keep=2)
    with pytest.raises(ValueError):
        backup(db, dest, keep=0)
    assert first.exists()


def test_restore_on_a_copy_brings_the_data_back(tmp_path):
    db = _db(tmp_path)
    copy = backup(db, tmp_path / "backups", keep=7)
    with Database(db).connect(write=True) as conn:
        conn.execute("DELETE FROM users")
    Path(str(db) + "-wal").write_bytes(b"stale")   # a leftover log must not be replayed onto the copy
    restore(copy, db)
    assert _emails(db) == ["a@x.io"]
    assert not Path(str(db) + "-wal").exists()
    assert _emails(db.with_name("eloquence.db.before")) == []
    with Database(db).connect() as conn:   # the app opens it as normal
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 1


def test_restore_refuses_a_damaged_copy(tmp_path):
    db = _db(tmp_path)
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"x" * 4096)
    with pytest.raises(sqlite3.DatabaseError):
        restore(bad, db)
    assert _emails(db) == ["a@x.io"]


def test_script_backs_up_db_path_into_backup_dir(tmp_path):
    db = _db(tmp_path)
    env = {**os.environ, "DB_PATH": str(db), "BACKUP_DIR": str(tmp_path / "out")}
    run = subprocess.run([sys.executable, "scripts/backup_db.py"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    [copy] = (tmp_path / "out").glob("eloquence-*.db")
    assert _emails(copy) == ["a@x.io"]


@pytest.mark.skipif(not Path("/usr/bin/bash").exists() and not Path("/bin/bash").exists(), reason="needs bash")
def test_installer_writes_units_once(tmp_path):
    units = tmp_path / "units"
    units.mkdir()
    log = tmp_path / "calls"
    fake = tmp_path / "fake-sudo"   # stands in for "sudo -n": records systemctl calls, runs tee
    fake.write_text(f'#!/bin/sh\nif [ "$1" = systemctl ]; then echo "$@" >> {log}; exit 0; fi\nexec "$@"\n')
    fake.chmod(0o755)
    env = {**os.environ, "UNITS": str(units), "SUDO": str(fake), "RUN_AS": "eloquence"}
    for _ in range(2):
        run = subprocess.run(["bash", "scripts/install_backup.sh"], cwd=ROOT, env=env, capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
    service = (units / "eloquence-backup.service").read_text()
    assert f"WorkingDirectory={ROOT}" in service and "scripts/backup_db.py" in service and "User=eloquence" in service
    assert "OnCalendar=*-*-* 03:15:00" in (units / "eloquence-backup.timer").read_text()
    calls = log.read_text().splitlines()
    assert calls.count("systemctl daemon-reload") == 1   # the second run found nothing to change
    assert calls.count("systemctl enable --now -q eloquence-backup.timer") == 2
