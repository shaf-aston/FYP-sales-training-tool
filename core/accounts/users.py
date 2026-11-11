"""Learner accounts: sign up, log in, look up and delete. Email is the login, case-insensitive."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from core.accounts.db import Database
from core.accounts.passwords import check_password, hash_password
from core.accounts.teams import keep_a_manager
from core.infra.constants import MAX_ACCOUNT_NAME_CHARS, MAX_EMAIL_CHARS, MIN_PASSWORD_CHARS

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# A password check that always runs, so a login for an unknown email takes as long as a wrong password.
_DUMMY_HASH = hash_password("timing-equaliser")


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

    def to_json(self) -> dict:
        return {"id": self.id, "email": self.email, "name": self.name}


def _user(row) -> User | None:
    return User(row["id"], row["email"], row["name"], row["created_at"]) if row else None


def check_signup(email: str, name: str, password: str) -> tuple[str, str]:
    """(email, name) cleaned, or AccountError naming the first field to fix."""
    email, name = (email or "").strip(), " ".join((name or "").split())
    if not _EMAIL.match(email) or len(email) > MAX_EMAIL_CHARS:
        raise AccountError("email", "invalid")
    if not name or len(name) > MAX_ACCOUNT_NAME_CHARS:
        raise AccountError("name", "invalid")
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_CHARS:
        raise AccountError("password", "too_short")
    return email, name


class Users:
    def __init__(self, db: Database):
        self.db = db

    def create(self, email: str, name: str, password: str) -> User:
        email, name = check_signup(email, name, password)
        with self.db.connect() as conn:
            if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                raise AccountError("email", "taken")
            now = int(time.time())
            cur = conn.execute(
                "INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (email, name, hash_password(password), now),
            )
            return User(cur.lastrowid, email, name, now)

    def authenticate(self, email: str, password: str) -> User | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", ((email or "").strip(),)).fetchone()
        ok = check_password(password or "", row["password_hash"] if row else _DUMMY_HASH)
        return _user(row) if row and ok else None

    def get(self, user_id: int) -> User | None:
        with self.db.connect() as conn:
            return _user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())

    def delete(self, user_id: int) -> None:
        """The user and everything kept for them (membership, skill history, prospects); their team keeps a manager."""
        with self.db.connect() as conn:
            team = conn.execute("SELECT team_id FROM memberships WHERE user_id = ?", (user_id,)).fetchone()
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            if team:
                keep_a_manager(conn, team["team_id"])
