"""Learner accounts: sign up, log in, look up and delete. Email is the login, case-insensitive.

Signing up with an email that has an account says so ("log in instead"): a deliberate choice for a training app,
where a clear message beats hiding which emails are registered. Logging in never says which part was wrong.
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass

from core.accounts.db import Database
from core.accounts.passwords import check_password, hash_password
from core.accounts.teams import keep_a_manager
from core.infra.constants import MAX_ACCOUNT_NAME_CHARS, MAX_EMAIL_CHARS, MAX_PASSWORD_CHARS, MIN_PASSWORD_CHARS

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# A password check that always runs, so a login for an unknown email takes as long as a wrong password.
_DUMMY_HASH = hash_password("timing-equaliser")
# Stored for an account with no password: never a valid scrypt hash, so no password ever matches it.
_NO_PASSWORD = "none"


class AccountError(ValueError):
    """Sign-up refused. `field` names what to fix: email, name or password."""

    def __init__(self, field: str, code: str):
        super().__init__(f"{field}: {code}")
        self.field, self.code = field, code


@dataclass(frozen=True)
class User:
    id: int
    email: str
    name: str
    created_at: int
    session_version: int = 1
    has_password: bool = True   # False: made by an email link or Google, signs in only that way

    def to_json(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name, "created_at": self.created_at,
                "has_password": self.has_password}


def _user(row) -> User | None:
    return User(row["id"], row["email"], row["name"], row["created_at"], row["session_version"],
                bool(row["has_password"])) if row else None


def check_email(email) -> str:
    """The email cleaned, or AccountError("email", "invalid")."""
    email = email.strip() if isinstance(email, str) else ""
    if not _EMAIL.match(email) or len(email) > MAX_EMAIL_CHARS:
        raise AccountError("email", "invalid")
    return email


def check_signup(email, name, password) -> tuple[str, str]:
    """(email, name) cleaned, or AccountError naming the first field to fix. Anything not text is invalid."""
    email = check_email(email)
    name = " ".join(name.split()) if isinstance(name, str) else ""
    if not name or len(name) > MAX_ACCOUNT_NAME_CHARS:
        raise AccountError("name", "invalid")
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_CHARS:
        raise AccountError("password", "too_short")
    if len(password) > MAX_PASSWORD_CHARS:
        raise AccountError("password", "too_long")
    return email, name


class Users:
    def __init__(self, db: Database):
        self.db = db

    def create(self, email, name, password) -> User:
        email, name = check_signup(email, name, password)
        hashed = hash_password(password)   # slow: done before taking the write lock
        now = int(time.time())
        try:
            with self.db.connect(write=True) as conn:
                if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                    raise AccountError("email", "taken")
                cur = conn.execute("INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                                   (email, name, hashed, now))
        except sqlite3.IntegrityError as e:   # another request signed this email up first
            raise AccountError("email", "taken") from e
        return User(cur.lastrowid, email, name, now)

    def find_or_create(self, email: str, name: str | None = None) -> User:
        """The account for an email someone proved they own (an email link, Google): theirs if it exists, else a
        new one with no password. `name` defaults to the part before the @."""
        email = check_email(email)
        clean = " ".join((name or "").split())[:MAX_ACCOUNT_NAME_CHARS] or email.split("@")[0][:MAX_ACCOUNT_NAME_CHARS]
        with self.db.connect(write=True) as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if row is None:
                conn.execute("INSERT INTO users (email, name, password_hash, created_at, has_password) "
                             "VALUES (?, ?, ?, ?, 0)", (email, clean, _NO_PASSWORD, int(time.time())))
                row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return _user(row)

    def authenticate(self, email, password) -> User | None:
        """The user when email and password match, else None (also for anything that is not text)."""
        if not isinstance(email, str) or not isinstance(password, str) or len(password) > MAX_PASSWORD_CHARS:
            check_password("", _DUMMY_HASH)
            return None
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip(),)).fetchone()
        usable = row is not None and bool(row["has_password"])
        ok = check_password(password, row["password_hash"] if usable else _DUMMY_HASH)   # same time either way
        return _user(row) if usable and ok else None

    def get(self, user_id: int) -> User | None:
        with self.db.connect() as conn:
            return _user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())

    def end_sessions(self, user_id: int) -> None:
        """Every login of this user stops working (their cookies carry the old version)."""
        with self.db.connect(write=True) as conn:
            conn.execute("UPDATE users SET session_version = session_version + 1 WHERE id = ?", (user_id,))

    def delete(self, user_id: int) -> None:
        """The user and everything kept for them (membership, skill history, prospects), overwritten on disk;
        their team keeps a manager."""
        with self.db.connect(write=True) as conn:
            team = conn.execute("SELECT team_id FROM memberships WHERE user_id = ?", (user_id,)).fetchone()
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            if team:
                keep_a_manager(conn, team["team_id"])
        self.db.checkpoint()
