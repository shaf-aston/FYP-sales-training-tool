"""Who is logged in: a signed session cookie holding the user id and their session version, and the decorator
routes use to require a login.

The cookie is HttpOnly, SameSite=Lax (other sites cannot post with it) and Secure unless COOKIE_SECURE=0 (local
http). Logging out or deleting the account bumps the user's session version, so every copy of their cookie stops
working, not only this browser's. The signing key is SECRET_KEY, else a random key written once to
data/.secret_key, so logins survive restarts without setup. The web reaches the API through the Vercel rewrite,
so the cookie is first-party.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, session

from core.accounts.db import database
from core.accounts.users import User, Users
from core.infra.constants import LOGIN_FAILURE_WINDOW_SECONDS, LOGIN_FAILURES, SESSION_DAYS
from core.infra.env import ROOT_DIR, env_flag, env_str

from .messages import LOGIN_REQUIRED

_KEY_FILE = ROOT_DIR / "data" / ".secret_key"
_MIN_KEY_CHARS = 32


def _secret_key(path: Path = _KEY_FILE) -> str:
    """SECRET_KEY, else the key file; a missing or too-short file gets a new key, written whole (temp file then
    rename) so a crash or a second process never leaves a half-written key."""
    key = env_str("SECRET_KEY")
    if key:
        return key
    existing = path.read_text("utf-8").strip() if path.is_file() else ""
    if len(existing) >= _MIN_KEY_CHARS:
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{os.getpid()}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(secrets.token_hex(32))
    os.replace(temp, path)
    return path.read_text("utf-8").strip()   # whichever process renamed last: every process reads the same key


def init_auth(app: Flask) -> None:
    app.secret_key = _secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=env_flag("COOKIE_SECURE", True),
        PERMANENT_SESSION_LIFETIME=timedelta(days=SESSION_DAYS),
    )


def log_in(user: User) -> None:
    session.clear()   # a fresh session on every login: nothing from before it carries over
    session.permanent = True
    session["uid"], session["sv"] = user.id, user.session_version


def log_out(user: User | None = None) -> None:
    """End this login; with `user`, end every login of theirs (all their cookies carry the old version)."""
    if user is not None:
        Users(database()).end_sessions(user.id)
    session.clear()


def current_user() -> User | None:
    """The logged-in user, looked up once per request; None when logged out, the account is gone, or the cookie
    is from before a log-out."""
    if "user" not in g:
        uid, version = session.get("uid"), session.get("sv")
        user = Users(database()).get(uid) if isinstance(uid, int) else None
        g.user = user if user and user.session_version == version else None
    return g.user


def require_user(view):
    """The view gets the logged-in User as its first argument; 401 otherwise."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": LOGIN_REQUIRED, "code": "LOGIN_REQUIRED"}), 401
        return view(user, *args, **kwargs)

    return wrapper


class LoginThrottle:
    """Wrong passwords per email: after LOGIN_FAILURES within the window, that email cannot log in until the
    oldest failure ages out. Keyed by email, not IP, so it holds whatever the proxy does to client addresses.
    In process memory: the server runs one process (gunicorn.conf.py)."""

    def __init__(self, limit: int = LOGIN_FAILURES, window: float = LOGIN_FAILURE_WINDOW_SECONDS):
        self.limit, self.window = limit, window
        self._failures: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque:
        failures = self._failures[key]
        while failures and now - failures[0] > self.window:
            failures.popleft()
        return failures

    def locked(self, email: str) -> bool:
        with self._lock:
            return len(self._recent(email.strip().lower(), time.monotonic())) >= self.limit

    def failed(self, email: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._recent(email.strip().lower(), now).append(now)

    def succeeded(self, email: str) -> None:
        with self._lock:
            self._failures.pop(email.strip().lower(), None)


login_throttle = LoginThrottle()
