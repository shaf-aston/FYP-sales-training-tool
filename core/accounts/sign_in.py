"""Signing in without a password: a one-time link by email, or Google. Both prove the learner owns an email; the
account for it is found or made (Users.find_or_create), with no password when it is new.

Email links: only a hash of each token is kept, a link works once and for `link_minutes`, and an address gets at most
`links_per_window` links per window, so the form cannot be used to flood someone's inbox. Google: the standard
authorisation-code flow; the ID token comes straight from Google's token endpoint over HTTPS (so, as Google's guide
allows, its claims are checked rather than its signature): our client id, Google as issuer, not expired, a verified
email.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import urllib.request
from collections.abc import Callable

from core.accounts.db import Database

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class SignInError(ValueError):
    """`code`: too_many (links), bad_token, google (the exchange or the token failed a check)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SignInLinks:
    def __init__(self, db: Database, minutes: int, per_window: int, window_minutes: int):
        self.db, self.ttl, self.per_window, self.window = db, minutes * 60, per_window, window_minutes * 60

    def create(self, email: str, now: int | None = None) -> str:
        """A new one-time token for `email` (already checked). Raises SignInError("too_many")."""
        now = int(now if now is not None else time.time())
        token = secrets.token_urlsafe(32)
        with self.db.connect(write=True) as conn:
            recent = conn.execute("SELECT COUNT(*) FROM sign_in_links WHERE email = ? AND created_at > ?",
                                  (email, now - self.window)).fetchone()[0]
            if recent >= self.per_window:
                raise SignInError("too_many")
            conn.execute("DELETE FROM sign_in_links WHERE expires_at < ?", (now - self.window,))
            conn.execute("INSERT INTO sign_in_links (token_hash, email, created_at, expires_at) VALUES (?, ?, ?, ?)",
                         (_hash(token), email, now, now + self.ttl))
        return token

    def use(self, token, now: int | None = None) -> str:
        """The email a live, unused token was made for; the token is spent. Raises SignInError("bad_token")."""
        now = int(now if now is not None else time.time())
        if not isinstance(token, str) or not 20 <= len(token) <= 100:
            raise SignInError("bad_token")
        with self.db.connect(write=True) as conn:
            row = conn.execute("SELECT email FROM sign_in_links WHERE token_hash = ? AND used_at IS NULL AND expires_at >= ?",
                               (_hash(token), now)).fetchone()
            if row is None:
                raise SignInError("bad_token")
            conn.execute("UPDATE sign_in_links SET used_at = ? WHERE token_hash = ?", (now, _hash(token)))
        return row["email"]


# --- Google ---

Post = Callable[[str, dict], dict]


def _post_form(url: str, fields: dict) -> dict:
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as res:   # noqa: S310 (a fixed https URL)
        return json.loads(res.read().decode("utf-8"))


def google_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    return GOOGLE_AUTH + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": "openid email profile", "state": state, "prompt": "select_account",
    })


def _claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        raise SignInError("google") from None


def google_identity(code: str, client_id: str, secret: str, redirect_uri: str, post: Post = _post_form,
                    now: int | None = None) -> tuple[str, str | None]:
    """(email, name) for the Google account that approved `code`. Raises SignInError("google")."""
    try:
        tokens = post(GOOGLE_TOKEN, {"code": code, "client_id": client_id, "client_secret": secret,
                                     "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
    except Exception:
        raise SignInError("google") from None
    claims = _claims(str(tokens.get("id_token", "")))
    now = int(now if now is not None else time.time())
    if (claims.get("aud") != client_id or claims.get("iss") not in _GOOGLE_ISSUERS
            or not isinstance(claims.get("exp"), int) or claims["exp"] < now
            or claims.get("email_verified") is not True or not isinstance(claims.get("email"), str)):
        raise SignInError("google")
    name = claims.get("name")
    return claims["email"], name if isinstance(name, str) else None
