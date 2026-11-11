"""Account endpoints (/api/account): sign up, log in and out, who am I, delete or export everything, and what is
kept for the learner (skill history, saved prospects). The data lives in core/accounts; this file decides access.
"""

from flask import Blueprint, jsonify, request

from core.accounts.db import database
from core.accounts.library import Library, LibraryError
from core.accounts.teams import Teams
from core.accounts.users import AccountError, Users
from core.infra.constants import MAX_SAVED_PROSPECTS, MAX_SKILL_ENTRIES
from core.sell_mode.custom_buyer import InvalidCustomBuyer, parse_custom_buyer

from ..auth import current_user, log_in, log_out, require_user
from ..messages import (
    ACCOUNT_FIELD_ERRORS,
    BAD_LOGIN,
    CUSTOM_BUYER_INVALID,
    PASSWORD_WRONG,
    PROSPECT_NOT_FOUND,
    PROSPECTS_FULL,
    SKILL_ENTRIES_INVALID,
)
from ..security import require_rate_limit

bp = Blueprint("account", __name__, url_prefix="/api/account")


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _me(user) -> dict:
    membership = Teams(database()).membership(user.id) if user else None
    return {
        "user": user.to_json() if user else None,
        "team": membership.to_json(show_code=membership.role == "manager") if membership else None,
    }


@bp.route("/me", methods=["GET"])
def me():
    """The logged-in learner and their team, or nulls when logged out (never 401: the web asks on every load)."""
    return jsonify({"success": True, **_me(current_user())})


@bp.route("/signup", methods=["POST"])
@require_rate_limit("account")
def signup():
    data = _body()
    try:
        user = Users(database()).create(data.get("email"), data.get("name"), data.get("password"))
    except AccountError as e:
        return jsonify({"error": ACCOUNT_FIELD_ERRORS[(e.field, e.code)], "field": e.field, "code": e.code}), 400
    log_in(user)
    return jsonify({"success": True, **_me(user)}), 201


@bp.route("/login", methods=["POST"])
@require_rate_limit("account")
def login():
    data = _body()
    user = Users(database()).authenticate(data.get("email"), data.get("password"))
    if user is None:
        return jsonify({"error": BAD_LOGIN, "code": "BAD_LOGIN"}), 401
    log_in(user)
    return jsonify({"success": True, **_me(user)})


@bp.route("/logout", methods=["POST"])
def logout():
    log_out()
    return jsonify({"success": True})


@bp.route("/delete", methods=["POST"])
@require_rate_limit("account")
@require_user
def delete(user):
    """Delete the account and everything kept for it. Asks for the password, so a left-open laptop can't."""
    if Users(database()).authenticate(user.email, _body().get("password")) is None:
        return jsonify({"error": PASSWORD_WRONG, "code": "PASSWORD_WRONG"}), 403
    Users(database()).delete(user.id)
    log_out()
    return jsonify({"success": True})


@bp.route("/export", methods=["GET"])
@require_user
def export(user):
    """Everything kept for the learner, as one JSON document."""
    library = Library(database())
    return jsonify({"success": True, **_me(user), "skills": library.skill_entries(user.id),
                    "prospects": library.prospects(user.id)})


# --- skill history ---


@bp.route("/skills", methods=["GET"])
@require_user
def skills(user):
    return jsonify({"success": True, "entries": Library(database()).skill_entries(user.id)})


@bp.route("/skills", methods=["POST"])
@require_user
def add_skills(user):
    """Store scored sessions (`entries`, the web's skill log shape). The web sends its device log once after login,
    then each new session, so history made before logging in is kept."""
    entries = _body().get("entries")
    if not isinstance(entries, list) or len(entries) > MAX_SKILL_ENTRIES:
        return jsonify({"error": SKILL_ENTRIES_INVALID.format(max=MAX_SKILL_ENTRIES)}), 400
    try:
        stored = Library(database()).add_skill_entries(user.id, entries)
    except LibraryError:
        return jsonify({"error": SKILL_ENTRIES_INVALID.format(max=MAX_SKILL_ENTRIES)}), 400
    return jsonify({"success": True, "stored": stored})


# --- saved prospects ---


@bp.route("/prospects", methods=["GET"])
@require_user
def prospects(user):
    return jsonify({"success": True, "prospects": Library(database()).prospects(user.id)})


@bp.route("/prospects", methods=["POST"])
@require_user
def save_prospect(user):
    """Save a custom buyer (the shape /api/sell/init takes as `custom_buyer`) to practise against again."""
    try:
        persona, bank = parse_custom_buyer(_body().get("profile"))
    except InvalidCustomBuyer as e:
        return jsonify({"error": CUSTOM_BUYER_INVALID.format(detail=e)}), 400
    profile = {k: v for k, v in persona.items() if k != "custom"} | {"objections": bank}
    try:
        saved = Library(database()).save_prospect(user.id, profile)
    except LibraryError:
        return jsonify({"error": PROSPECTS_FULL.format(max=MAX_SAVED_PROSPECTS)}), 400
    return jsonify({"success": True, "prospect": saved}), 201


@bp.route("/prospects/<int:prospect_id>", methods=["DELETE"])
@require_user
def delete_prospect(user, prospect_id):
    if not Library(database()).delete_prospect(user.id, prospect_id):
        return jsonify({"error": PROSPECT_NOT_FOUND}), 404
    return jsonify({"success": True})
