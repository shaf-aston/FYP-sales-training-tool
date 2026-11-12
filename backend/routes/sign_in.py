"""Signing in without a password (/api/account): a one-time link by email, or Google (core/accounts/sign_in.py).

Each is on only when its settings are there: email links need RESEND_API_KEY, MAIL_FROM and SITE_URL; Google needs
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and SITE_URL (docs/SETUP.md). The web asks /sign-in-options and shows only
what is on. Links and Google come back to SITE_URL/buy/, where the web finishes signing in.
"""

import hmac
import secrets

from flask import Blueprint, jsonify, redirect, request, session

from core.accounts.db import database
from core.accounts.sign_in import SignInError, SignInLinks, google_auth_url, google_identity
from core.accounts.users import AccountError, Users, check_email
from core.infra.constants import SIGN_IN_LINKS
from core.infra.env import env_str
from core.infra.mail import mail_ready, send_mail

from ..auth import log_in
from ..messages import LINK_EMAIL_INVALID, LINK_INVALID, LINK_LIMIT, LINK_NOT_SENT, SIGN_IN_OFF
from ..security import require_rate_limit
from ._utils import json_body
from .account import _me

bp = Blueprint("sign_in", __name__, url_prefix="/api/account")

_RETURN = "/buy/"   # where the web finishes signing in (it reads ?signin= and ?signedin=)


def _site() -> str:
    return (env_str("SITE_URL") or "").rstrip("/")


def links_on() -> bool:
    return bool(_site()) and mail_ready()


def google_on() -> bool:
    return bool(_site() and env_str("GOOGLE_CLIENT_ID") and env_str("GOOGLE_CLIENT_SECRET"))


def _links() -> SignInLinks:
    return SignInLinks(database(), SIGN_IN_LINKS["minutes"], SIGN_IN_LINKS["per_window"], SIGN_IN_LINKS["window_minutes"])


def _off():
    return jsonify({"error": SIGN_IN_OFF, "code": "SIGN_IN_OFF"}), 404


@bp.route("/sign-in-options", methods=["GET"])
def options():
    return jsonify({"success": True, "link": links_on(), "google": google_on()})


@bp.route("/link", methods=["POST"])
@require_rate_limit("signup")
def send_link():
    """Email a one-time sign-in link. The answer is the same whether or not the address has an account."""
    if not links_on():
        return _off()
    try:
        email = check_email(json_body().get("email"))
    except AccountError:
        return jsonify({"error": LINK_EMAIL_INVALID, "field": "email", "code": "invalid"}), 400
    try:
        token = _links().create(email)
    except SignInError:
        return jsonify({"error": LINK_LIMIT, "code": "LINK_LIMIT"}), 429
    link = f"{_site()}{_RETURN}?signin={token}"
    minutes = SIGN_IN_LINKS["minutes"]
    try:
        send_mail(email, "Your Eloquence sign-in link",
                  f"Open this link to sign in to Eloquence:\n\n{link}\n\nIt works once, for {minutes} minutes. "
                  "If you didn't ask for it, ignore this email.")
    except Exception:
        return jsonify({"error": LINK_NOT_SENT, "code": "LINK_NOT_SENT"}), 502
    return jsonify({"success": True, "minutes": minutes})


@bp.route("/link/use", methods=["POST"])
@require_rate_limit("login")
def use_link():
    """Sign in with a link's token (the web posts it, so an email scanner opening the link spends nothing)."""
    try:
        email = _links().use(json_body().get("token"))
    except SignInError:
        return jsonify({"error": LINK_INVALID, "code": "LINK_INVALID"}), 400
    user = Users(database()).find_or_create(email)
    log_in(user)
    return jsonify({"success": True, **_me(user)})


@bp.route("/google", methods=["GET"])
def google_start():
    if not google_on():
        return _off()
    state = secrets.token_urlsafe(24)
    session["google_state"] = state
    return redirect(google_auth_url(env_str("GOOGLE_CLIENT_ID"), f"{_site()}/api/account/google/callback", state))


@bp.route("/google/callback", methods=["GET"])
@require_rate_limit("login")
def google_back():
    if not google_on():
        return _off()
    expected, state, code = session.pop("google_state", None), request.args.get("state", ""), request.args.get("code")
    if not expected or not code or not hmac.compare_digest(str(expected), state):
        return redirect(f"{_site()}{_RETURN}?signin_error=google")
    try:
        email, name = google_identity(code, env_str("GOOGLE_CLIENT_ID"), env_str("GOOGLE_CLIENT_SECRET"),
                                      f"{_site()}/api/account/google/callback")
        user = Users(database()).find_or_create(email, name)
    except (SignInError, AccountError):
        return redirect(f"{_site()}{_RETURN}?signin_error=google")
    log_in(user)
    return redirect(f"{_site()}{_RETURN}?signedin=google")
