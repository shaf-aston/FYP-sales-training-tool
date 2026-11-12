"""Signing in without a password: one-time email links and Google. Off until their settings exist."""

import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest

from backend.app import app
from core.accounts.sign_in import SignInError, google_identity

SITE = "https://site.example"


@pytest.fixture
def c():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def mail(monkeypatch):
    """Email links on, with the mail service replaced: each sent email lands in the list."""
    sent = []
    for name, value in {"SITE_URL": SITE, "RESEND_API_KEY": "test", "MAIL_FROM": "Eloquence <hi@site.example>"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("backend.routes.sign_in.send_mail", lambda to, subject, text: sent.append((to, text)))
    return sent


def token_in(text):
    return parse_qs(urlparse(next(w for w in text.split() if w.startswith(SITE))).query)["signin"][0]


def test_both_are_off_without_their_settings(c, monkeypatch):
    for name in ("SITE_URL", "RESEND_API_KEY", "MAIL_FROM", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    assert c.get("/api/account/sign-in-options").get_json() == {"success": True, "link": False, "google": False}
    assert c.post("/api/account/link", json={"email": "a@x.co"}).status_code == 404
    assert c.get("/api/account/google").status_code == 404


def test_an_email_link_signs_in_once_and_makes_a_password_less_account(c, mail):
    assert c.get("/api/account/sign-in-options").get_json()["link"] is True
    assert c.post("/api/account/link", json={"email": "New@X.co"}).status_code == 200
    (to, text), = mail
    assert to == "New@X.co" and f"{SITE}/buy/?signin=" in text
    token = token_in(text)
    me = c.post("/api/account/link/use", json={"token": token}).get_json()
    assert me["user"]["email"] == "New@X.co" and me["user"]["has_password"] is False and me["user"]["name"] == "New"
    assert c.get("/api/account/me").get_json()["user"]["email"] == "New@X.co"
    again = app.test_client().post("/api/account/link/use", json={"token": token})
    assert again.status_code == 400 and again.get_json()["code"] == "LINK_INVALID"
    # no password matches an account made this way
    assert app.test_client().post("/api/account/login", json={"email": "new@x.co", "password": "none"}).status_code == 401


def test_a_link_for_an_existing_account_signs_into_it(c, mail):
    c.post("/api/account/signup", json={"email": "ann@x.co", "name": "Ann", "password": "longenough"})
    c.post("/api/account/link", json={"email": "ann@x.co"})
    other = app.test_client()
    me = other.post("/api/account/link/use", json={"token": token_in(mail[0][1])}).get_json()
    assert me["user"]["name"] == "Ann" and me["user"]["has_password"] is True


def test_links_expire_and_an_address_gets_only_a_few(c, mail, monkeypatch):
    c.post("/api/account/link", json={"email": "a@x.co"})
    later = time.time() + 16 * 60
    monkeypatch.setattr("core.accounts.sign_in.time.time", lambda: later)
    assert c.post("/api/account/link/use", json={"token": token_in(mail[0][1])}).status_code == 400
    monkeypatch.undo()
    for name, value in {"SITE_URL": SITE, "RESEND_API_KEY": "test", "MAIL_FROM": "x@site.example"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("backend.routes.sign_in.send_mail", lambda *a: None)
    codes = [c.post("/api/account/link", json={"email": "b@x.co"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


@pytest.mark.parametrize("token", [None, 5, "short", "x" * 300, "a" * 43])
def test_a_bad_token_is_refused(c, token):
    assert c.post("/api/account/link/use", json={"token": token}).status_code == 400


def test_a_bad_address_or_a_failed_send_says_so(c, mail, monkeypatch):
    assert c.post("/api/account/link", json={"email": "not-an-email"}).status_code == 400

    def broken(*a):
        raise OSError("down")
    monkeypatch.setattr("backend.routes.sign_in.send_mail", broken)
    assert c.post("/api/account/link", json={"email": "a@x.co"}).get_json()["code"] == "LINK_NOT_SENT"


def test_a_password_less_account_deletes_only_soon_after_signing_in(c, mail):
    c.post("/api/account/link", json={"email": "gone@x.co"})
    c.post("/api/account/link/use", json={"token": token_in(mail[0][1])})
    with c.session_transaction() as sess:
        signed_in = sess["at"]
        sess["at"] = signed_in - 11 * 60   # signed in 11 minutes ago
    res = c.post("/api/account/delete", json={})
    assert res.status_code == 403 and res.get_json()["code"] == "SIGN_IN_AGAIN"
    with c.session_transaction() as sess:
        sess["at"] = signed_in
    assert c.post("/api/account/delete", json={}).status_code == 200
    assert c.get("/api/account/me").get_json()["user"] is None


# --- Google ---

def id_token(**claims):
    body = {"aud": "cid", "iss": "https://accounts.google.com", "exp": int(time.time()) + 600,
            "email": "g@x.co", "email_verified": True, "name": "Gee Whiz", **claims}
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{enc({'alg': 'RS256'})}.{enc(body)}.sig"


def test_google_gives_the_verified_email_and_name():
    post = lambda url, fields: {"id_token": id_token()} if fields["client_secret"] == "sec" else {}
    assert google_identity("code", "cid", "sec", "https://r", post) == ("g@x.co", "Gee Whiz")


@pytest.mark.parametrize("claims", [{"aud": "other"}, {"iss": "https://evil.example"}, {"exp": 1},
                                    {"email_verified": False}, {"email": None}])
def test_google_refuses_a_token_that_fails_a_check(claims):
    with pytest.raises(SignInError):
        google_identity("code", "cid", "sec", "https://r", lambda url, fields: {"id_token": id_token(**claims)})


def test_google_refuses_when_the_exchange_fails():
    def broken(url, fields):
        raise OSError("no")
    with pytest.raises(SignInError):
        google_identity("code", "cid", "sec", "https://r", broken)


@pytest.fixture
def google(monkeypatch):
    for name, value in {"SITE_URL": SITE, "GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "sec"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("backend.routes.sign_in.google_identity", lambda code, *a: ("g@x.co", "Gee Whiz"))


def test_google_sign_in_round_trip(c, google):
    start = c.get("/api/account/google")
    assert start.status_code == 302 and start.location.startswith("https://accounts.google.com/")
    query = parse_qs(urlparse(start.location).query)
    assert query["redirect_uri"] == [f"{SITE}/api/account/google/callback"] and query["client_id"] == ["cid"]
    back = c.get(f"/api/account/google/callback?code=abc&state={query['state'][0]}")
    assert back.location == f"{SITE}/buy/?signedin=google"
    assert c.get("/api/account/me").get_json()["user"]["name"] == "Gee Whiz"


def test_google_callback_without_our_state_signs_nobody_in(c, google):
    c.get("/api/account/google")
    back = c.get("/api/account/google/callback?code=abc&state=forged")
    assert back.location == f"{SITE}/buy/?signin_error=google"
    assert c.get("/api/account/me").get_json()["user"] is None
    assert app.test_client().get("/api/account/google/callback?code=abc&state=").location.endswith("signin_error=google")
