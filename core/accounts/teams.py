"""Teams: a manager creates one and shares its invite code; reps join with it. A learner is in at most one team.
Managers see their reps' skill history (backend/routes/team.py); reps see only their own."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

from core.accounts.db import Database
from core.infra.constants import MAX_TEAM_NAME_CHARS

REP, MANAGER = "rep", "manager"
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I: read aloud or typed from a screen
_CODE_LENGTH = 8


class TeamError(ValueError):
    """`code`: name_invalid, already_in_team, unknown_code or not_in_team."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Membership:
    team_id: int
    team_name: str
    invite_code: str
    role: str

    def to_json(self, show_code: bool) -> dict:
        return {"id": self.team_id, "name": self.team_name, "role": self.role,
                "invite_code": self.invite_code if show_code else None}


@dataclass(frozen=True)
class Member:
    user_id: int
    name: str
    email: str
    role: str


def keep_a_manager(conn, team_id: int) -> None:
    """After someone leaves `team_id` (or their account is deleted): with members but no manager, the
    longest-standing rep becomes manager; with no members, the team is deleted."""
    if conn.execute("SELECT 1 FROM memberships WHERE team_id = ? AND role = ?", (team_id, MANAGER)).fetchone():
        return
    oldest = conn.execute("SELECT user_id FROM memberships WHERE team_id = ? ORDER BY joined_at, user_id LIMIT 1",
                          (team_id,)).fetchone()
    if oldest:
        conn.execute("UPDATE memberships SET role = ? WHERE user_id = ?", (MANAGER, oldest["user_id"]))
    else:
        conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))


def _code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


class Teams:
    def __init__(self, db: Database):
        self.db = db

    def membership(self, user_id: int) -> Membership | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT t.id, t.name, t.invite_code, m.role FROM memberships m JOIN teams t ON t.id = m.team_id "
                "WHERE m.user_id = ?", (user_id,),
            ).fetchone()
        return Membership(*row) if row else None

    def create(self, user_id: int, name: str) -> Membership:
        """A new team with `user_id` as its manager."""
        name = " ".join((name or "").split())
        if not name or len(name) > MAX_TEAM_NAME_CHARS:
            raise TeamError("name_invalid")
        with self.db.connect() as conn:
            if conn.execute("SELECT 1 FROM memberships WHERE user_id = ?", (user_id,)).fetchone():
                raise TeamError("already_in_team")
            now = int(time.time())
            code = _code()
            team_id = conn.execute("INSERT INTO teams (name, invite_code, created_at) VALUES (?, ?, ?)",
                                   (name, code, now)).lastrowid
            conn.execute("INSERT INTO memberships (user_id, team_id, role, joined_at) VALUES (?, ?, ?, ?)",
                         (user_id, team_id, MANAGER, now))
        return Membership(team_id, name, code, MANAGER)

    def join(self, user_id: int, invite_code: str) -> Membership:
        code = (invite_code or "").strip().upper()
        with self.db.connect() as conn:
            if conn.execute("SELECT 1 FROM memberships WHERE user_id = ?", (user_id,)).fetchone():
                raise TeamError("already_in_team")
            team = conn.execute("SELECT id, name, invite_code FROM teams WHERE invite_code = ?", (code,)).fetchone()
            if not team:
                raise TeamError("unknown_code")
            conn.execute("INSERT INTO memberships (user_id, team_id, role, joined_at) VALUES (?, ?, ?, ?)",
                         (user_id, team["id"], REP, int(time.time())))
        return Membership(team["id"], team["name"], team["invite_code"], REP)

    def leave(self, user_id: int) -> None:
        """Leave the team. A team is never left without a manager: when the last one leaves, the longest-standing
        rep becomes manager; when the last member leaves, the team is deleted."""
        with self.db.connect() as conn:
            row = conn.execute("SELECT team_id FROM memberships WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                raise TeamError("not_in_team")
            conn.execute("DELETE FROM memberships WHERE user_id = ?", (user_id,))
            keep_a_manager(conn, row["team_id"])

    def members(self, team_id: int) -> list[Member]:
        """Managers first, then reps, each by name."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT u.id, u.name, u.email, m.role FROM memberships m JOIN users u ON u.id = m.user_id "
                "WHERE m.team_id = ? ORDER BY m.role = 'manager' DESC, u.name COLLATE NOCASE", (team_id,),
            ).fetchall()
        return [Member(*r) for r in rows]
