"""Who is logged in: a signed session cookie holding the user id, and the decorator routes use to require it.

The cookie is HttpOnly, SameSite=Lax (other sites cannot post with it) and Secure unless COOKIE_SECURE=0 (local
http). The signing key is SECRET_KEY, else a random key written once to data/.secret_key, so logins survive
restarts without setup. The web reaches the API through the Vercel rewrite, so the cookie is first-party.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, session

from core.accounts.db import database
from core.accounts.users import User, Users
from core.infra.constants import SESSION_DAYS
from core.infra.env import ROOT_DIR, env_flag, env_str

from .messages import LOGIN_REQUIRED

_KEY_FILE = ROOT_DIR / "data" / ".secret_key"


def _secret_key(path: Path = _KEY_FILE) -> str:
    key = env_str("SECRET_KEY")
    if key:
        return key
    if path.is_file():
        return path.read_text("utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    path.touch(mode=0o600)
    path.write_text(key, "utf-8")
    return key


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
    session["uid"] = user.id


def log_out() -> None:
    session.clear()


def current_user() -> User | None:
    """The logged-in user, looked up once per request; None when logged out or the account is gone."""
    if "user" not in g:
        uid = session.get("uid")
        g.user = Users(database()).get(uid) if isinstance(uid, int) else None
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
