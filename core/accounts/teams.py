"""Teams: a manager creates one and shares its invite code; members join with it. A learner is in at most one team.
Managers see their members' details and skill history (backend/routes/team.py), can remove a member and replace
the invite code; members see the team's managers only."""

from __future__ import annotations

import json

import secrets
import sqlite3
import time
from dataclasses import dataclass

from core.accounts.db import Database
from core.infra.constants import INVITE_CODE_LENGTH, MAX_TEAM_NAME_CHARS

MEMBER, MANAGER = "member", "manager"
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I: read aloud or typed from a screen


class TeamError(ValueError):
    """`code`: name_invalid, already_in_team, unknown_code, not_in_team, not_manager or not_a_member."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Membership:
    team_id: int
    team_name: str
    invite_code: str
    role: str
    joined_at: int
    words: str | None = None   # the team's Rep's words, as JSON ({product, label, words, probes}); None: none set

    def to_json(self, show_code: bool) -> dict:
        return {"id": self.team_id, "name": self.team_name, "role": self.role, "joined_at": self.joined_at,
                "invite_code": self.invite_code if show_code else None,
                "words": json.loads(self.words) if self.words else None}


@dataclass(frozen=True)
class Member:
    user_id: int
    name: str
    email: str
    role: str


def keep_a_manager(conn, team_id: int) -> None:
    """After someone leaves `team_id` (or their account is deleted): with members but no manager, the
    longest-standing member becomes manager; with no members, the team is deleted."""
    if conn.execute("SELECT 1 FROM memberships WHERE team_id = ? AND role = ?", (team_id, MANAGER)).fetchone():
        return
    oldest = conn.execute("SELECT user_id FROM memberships WHERE team_id = ? ORDER BY joined_at, user_id LIMIT 1",
                          (team_id,)).fetchone()
    if oldest:
        conn.execute("UPDATE memberships SET role = ? WHERE user_id = ?", (MANAGER, oldest["user_id"]))
    else:
        conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))


def _code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


class Teams:
    def __init__(self, db: Database):
        self.db = db

    def membership(self, user_id: int) -> Membership | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT t.id, t.name, t.invite_code, m.role, m.joined_at, t.words FROM memberships m "
                "JOIN teams t ON t.id = m.team_id WHERE m.user_id = ?", (user_id,),
            ).fetchone()
        return Membership(*row) if row else None

    def create(self, user_id: int, name) -> Membership:
        """A new team with `user_id` as its manager."""
        name = " ".join(name.split()) if isinstance(name, str) else ""
        if not name or len(name) > MAX_TEAM_NAME_CHARS:
            raise TeamError("name_invalid")
        now, code = int(time.time()), _code()
        try:
            with self.db.connect(write=True) as conn:
                if conn.execute("SELECT 1 FROM memberships WHERE user_id = ?", (user_id,)).fetchone():
                    raise TeamError("already_in_team")
                team_id = conn.execute("INSERT INTO teams (name, invite_code, created_at) VALUES (?, ?, ?)",
                                       (name, code, now)).lastrowid
                conn.execute("INSERT INTO memberships (user_id, team_id, role, joined_at) VALUES (?, ?, ?, ?)",
                             (user_id, team_id, MANAGER, now))
        except sqlite3.IntegrityError as e:   # a double-click: the first request made the team
            raise TeamError("already_in_team") from e
        return Membership(team_id, name, code, MANAGER, now)

    def join(self, user_id: int, invite_code) -> Membership:
        code = invite_code.strip().upper() if isinstance(invite_code, str) else ""
        now = int(time.time())
        try:
            with self.db.connect(write=True) as conn:
                if conn.execute("SELECT 1 FROM memberships WHERE user_id = ?", (user_id,)).fetchone():
                    raise TeamError("already_in_team")
                team = conn.execute("SELECT id, name, invite_code, words FROM teams WHERE invite_code = ?", (code,)).fetchone()
                if not team:
                    raise TeamError("unknown_code")
                conn.execute("INSERT INTO memberships (user_id, team_id, role, joined_at) VALUES (?, ?, ?, ?)",
                             (user_id, team["id"], MEMBER, now))
        except sqlite3.IntegrityError as e:
            raise TeamError("already_in_team") from e
        return Membership(team["id"], team["name"], team["invite_code"], MEMBER, now, team["words"])

    def leave(self, user_id: int) -> None:
        """Leave the team. A team is never left without a manager: when the last one leaves, the longest-standing
        member becomes manager; when the last member leaves, the team is deleted."""
        with self.db.connect(write=True) as conn:
            row = conn.execute("SELECT team_id FROM memberships WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                raise TeamError("not_in_team")
            conn.execute("DELETE FROM memberships WHERE user_id = ?", (user_id,))
            keep_a_manager(conn, row["team_id"])

    def remove(self, manager_id: int, user_id: int) -> None:
        """A manager removes someone from their own team (themselves: use leave)."""
        with self.db.connect(write=True) as conn:
            team = self._managed(conn, manager_id)
            if user_id == manager_id or not conn.execute(
                    "SELECT 1 FROM memberships WHERE user_id = ? AND team_id = ?", (user_id, team)).fetchone():
                raise TeamError("not_a_member")
            conn.execute("DELETE FROM memberships WHERE user_id = ?", (user_id,))

    def new_code(self, manager_id: int) -> str:
        """Replace the invite code (the old one stops working), e.g. after it was shared too widely."""
        code = _code()
        with self.db.connect(write=True) as conn:
            conn.execute("UPDATE teams SET invite_code = ? WHERE id = ?", (code, self._managed(conn, manager_id)))
        return code

    def set_words(self, manager_id: int, choice: dict | None) -> None:
        """A manager sets the team's Rep's words (checked by the caller), or clears them with None. Members' new
        buy-mode calls use them unless they chose other words."""
        with self.db.connect(write=True) as conn:
            conn.execute("UPDATE teams SET words = ? WHERE id = ?",
                         (json.dumps(choice) if choice else None, self._managed(conn, manager_id)))

    def members(self, team_id: int) -> list[Member]:
        """Managers first, then members, each by name."""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT u.id, u.name, u.email, m.role FROM memberships m JOIN users u ON u.id = m.user_id "
                "WHERE m.team_id = ? ORDER BY m.role = 'manager' DESC, u.name COLLATE NOCASE", (team_id,),
            ).fetchall()
        return [Member(*r) for r in rows]

    @staticmethod
    def _managed(conn, user_id: int) -> int:
        """The team `user_id` manages, or TeamError("not_manager")."""
        row = conn.execute("SELECT team_id FROM memberships WHERE user_id = ? AND role = ?", (user_id, MANAGER)).fetchone()
        if not row:
            raise TeamError("not_manager")
        return row["team_id"]
