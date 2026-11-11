"""What is kept for one learner: their skill history (one entry per scored session) and saved prospects."""

from __future__ import annotations

import json
import time

from core.accounts.db import Database
from core.infra.constants import MAX_SAVED_PROSPECTS, MAX_SKILL_ENTRIES


class LibraryError(ValueError):
    """`code`: invalid or full."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def check_skill_entry(entry) -> tuple[str, int, int, dict]:
    """(session_id, at, overall, scores) from a posted entry, or LibraryError("invalid")."""
    if not isinstance(entry, dict):
        raise LibraryError("invalid")
    session_id, at, overall, scores = entry.get("sessionId"), entry.get("at"), entry.get("overall"), entry.get("scores")
    numbers = (overall, *(scores.values() if isinstance(scores, dict) else ()))
    if not (isinstance(session_id, str) and 0 < len(session_id) <= 128 and isinstance(at, int) and at > 0
            and isinstance(scores, dict) and 0 < len(scores) <= 20
            and all(isinstance(k, str) and len(k) <= 64 for k in scores)
            and all(isinstance(n, (int, float)) and not isinstance(n, bool) and 0 <= n <= 100 for n in numbers)):
        raise LibraryError("invalid")
    return session_id, at, round(overall), {k: round(v) for k, v in scores.items()}


class Library:
    def __init__(self, db: Database):
        self.db = db

    # --- skill history (the same shape the web keeps: features/skills/skillLog.ts SkillEntry) ---

    def add_skill_entries(self, user_id: int, entries: list) -> int:
        """Store entries (a session scored again replaces its entry); the oldest past the cap are dropped.
        Returns how many were stored. Raises LibraryError("invalid") before storing any if one is malformed."""
        rows = [check_skill_entry(e) for e in entries]
        with self.db.connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO skill_entries (user_id, session_id, at, overall, scores) VALUES (?, ?, ?, ?, ?)",
                [(user_id, s, at, o, json.dumps(sc)) for s, at, o, sc in rows],
            )
            conn.execute(
                "DELETE FROM skill_entries WHERE user_id = ? AND session_id NOT IN "
                "(SELECT session_id FROM skill_entries WHERE user_id = ? ORDER BY at DESC LIMIT ?)",
                (user_id, user_id, MAX_SKILL_ENTRIES),
            )
        return len(rows)

    def skill_entries(self, user_id: int) -> list[dict]:
        """Oldest first, as the web's skill log."""
        with self.db.connect() as conn:
            rows = conn.execute("SELECT session_id, at, overall, scores FROM skill_entries WHERE user_id = ? "
                                "ORDER BY at", (user_id,)).fetchall()
        return [{"sessionId": r["session_id"], "at": r["at"], "overall": r["overall"], "scores": json.loads(r["scores"])}
                for r in rows]

    # --- saved prospects (a custom buyer, e.g. built from an uploaded call) ---

    def save_prospect(self, user_id: int, profile: dict) -> dict:
        """`profile` is a custom buyer (checked by the caller with sell_mode.custom_buyer.parse_custom_buyer)."""
        with self.db.connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM prospects WHERE user_id = ?", (user_id,)).fetchone()[0] >= MAX_SAVED_PROSPECTS:
                raise LibraryError("full")
            now = int(time.time())
            pid = conn.execute("INSERT INTO prospects (user_id, name, profile, created_at) VALUES (?, ?, ?, ?)",
                               (user_id, profile["name"], json.dumps(profile), now)).lastrowid
        return {"id": pid, "name": profile["name"], "profile": profile, "created_at": now}

    def prospects(self, user_id: int) -> list[dict]:
        """Newest first."""
        with self.db.connect() as conn:
            rows = conn.execute("SELECT id, name, profile, created_at FROM prospects WHERE user_id = ? "
                                "ORDER BY created_at DESC, id DESC", (user_id,)).fetchall()
        return [{"id": r["id"], "name": r["name"], "profile": json.loads(r["profile"]), "created_at": r["created_at"]}
                for r in rows]

    def delete_prospect(self, user_id: int, prospect_id: int) -> bool:
        with self.db.connect() as conn:
            return conn.execute("DELETE FROM prospects WHERE id = ? AND user_id = ?", (prospect_id, user_id)).rowcount > 0
