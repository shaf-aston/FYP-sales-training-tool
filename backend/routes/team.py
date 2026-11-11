"""Team endpoints (/api/team): create one (you manage it), join with an invite code, leave, and see the team.
A manager sees every member; a rep sees the team's name and the managers only."""

from flask import Blueprint, jsonify, request

from core.accounts.db import database
from core.accounts.teams import MANAGER, TeamError, Teams

from ..auth import require_user
from ..messages import TEAM_ERRORS
from ..security import require_rate_limit

bp = Blueprint("team", __name__, url_prefix="/api/team")


def _error(e: TeamError):
    return jsonify({"error": TEAM_ERRORS[e.code], "code": e.code.upper()}), 400


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@bp.route("", methods=["GET"])
@require_user
def team(user):
    teams = Teams(database())
    membership = teams.membership(user.id)
    if membership is None:
        return jsonify({"success": True, "team": None, "members": []})
    manager = membership.role == MANAGER
    members = [m for m in teams.members(membership.team_id) if manager or m.role == MANAGER]
    return jsonify({
        "success": True,
        "team": membership.to_json(show_code=manager),
        "members": [{"id": m.user_id, "name": m.name, "role": m.role, **({"email": m.email} if manager else {})}
                    for m in members],
    })


@bp.route("/create", methods=["POST"])
@require_rate_limit("account")
@require_user
def create(user):
    try:
        membership = Teams(database()).create(user.id, _body().get("name"))
    except TeamError as e:
        return _error(e)
    return jsonify({"success": True, "team": membership.to_json(show_code=True)}), 201


@bp.route("/join", methods=["POST"])
@require_rate_limit("account")
@require_user
def join(user):
    try:
        membership = Teams(database()).join(user.id, _body().get("code"))
    except TeamError as e:
        return _error(e)
    return jsonify({"success": True, "team": membership.to_json(show_code=False)})


@bp.route("/leave", methods=["POST"])
@require_user
def leave(user):
    try:
        Teams(database()).leave(user.id)
    except TeamError as e:
        return _error(e)
    return jsonify({"success": True})
