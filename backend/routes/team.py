"""Team endpoints (/api/team): create one (you manage it), join with an invite code, leave, and see the team.
A manager sees every member's name and email and the invite code, removes members and replaces the code;
a member sees the team's name and its managers only. Managers also get insights: every member's skill levels and
coaching guidelines (core/training/team_insights.py), as JSON or a CSV download."""

import csv
import io
import time
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from core.accounts.db import database
from core.accounts.library import Library
from core.accounts.teams import MANAGER, TeamError, Teams
from core.infra.loader import load_yaml
from core.sell_mode import sell_service
from core.training.team_insights import build_insights

from ..auth import require_user
from ..messages import TEAM_ERRORS
from ..security import require_rate_limit
from ._utils import json_body

bp = Blueprint("team", __name__, url_prefix="/api/team")


def _error(e: TeamError):
    return jsonify({"error": TEAM_ERRORS[e.code], "code": e.code.upper()}), 400


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
@require_rate_limit("team")
@require_user
def create(user):
    try:
        membership = Teams(database()).create(user.id, json_body().get("name"))
    except TeamError as e:
        return _error(e)
    return jsonify({"success": True, "team": membership.to_json(show_code=True)}), 201


@bp.route("/join", methods=["POST"])
@require_rate_limit("team")
@require_user
def join(user):
    try:
        membership = Teams(database()).join(user.id, json_body().get("code"))
    except TeamError as e:
        return _error(e)
    return jsonify({"success": True, "team": membership.to_json(show_code=False)})


@bp.route("/leave", methods=["POST"])
@require_rate_limit("team")
@require_user
def leave(user):
    try:
        Teams(database()).leave(user.id)
    except TeamError as e:
        return _error(e)
    return jsonify({"success": True})


@bp.route("/remove", methods=["POST"])
@require_rate_limit("team")
@require_user
def remove(user):
    """A manager removes a member (`user_id`) from their team."""
    member = json_body().get("user_id")
    try:
        Teams(database()).remove(user.id, member if isinstance(member, int) else -1)
    except TeamError as e:
        return _error(e)
    return jsonify({"success": True})


@bp.route("/code", methods=["POST"])
@require_rate_limit("team")
@require_user
def new_code(user):
    """A manager replaces the invite code; the old one stops working."""
    try:
        code = Teams(database()).new_code(user.id)
    except TeamError as e:
        return _error(e)
    return jsonify({"success": True, "invite_code": code})


def _insights(user):
    """(insights, None) for a manager, else (None, error response). `?target=` picks one of the offered targets."""
    teams = Teams(database())
    membership = teams.membership(user.id)
    if membership is None or membership.role != MANAGER:
        return None, _error(TeamError("not_manager"))
    offered = sell_service.skills()
    target = request.args.get("target", type=int)
    target = target if target in offered["targets"] else offered["target"]
    library = Library(database())
    # A manager who doesn't practise is not a gap in the team: managers count once they have sessions of their own.
    members = []
    for m in teams.members(membership.team_id):   # read once: someone joining meanwhile can't break the view
        entries = library.skill_entries(m.user_id)
        if entries or m.role != MANAGER:
            members.append((m.user_id, m.name, entries))
    return build_insights(members, offered["skills"], target, int(time.time() * 1000), load_yaml("insights.yaml")), None


@bp.route("/insights", methods=["GET"])
@require_user
def insights(user):
    """A manager's view of the team: each member's skill levels, the team's, and what to coach next."""
    data, error = _insights(user)
    return error or jsonify({"success": True, "targets": sell_service.skills()["targets"], **data})


_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _cell(value):
    """A cell a spreadsheet shows as text: a name starting like a formula ("=HYPERLINK(...)") gets a leading '."""
    return f"'{value}" if isinstance(value, str) and value.startswith(_FORMULA_START) else value


@bp.route("/insights.csv", methods=["GET"])
@require_user
def insights_csv(user):
    """The same numbers as a spreadsheet: one row per member."""
    data, error = _insights(user)
    if error:
        return error
    skills = data["skills"]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Member", "Scored sessions", "Last practised", *[s["label"] for s in skills], "Work on next"])
    label = {s["id"]: s["label"] for s in skills}
    for m in data["members"]:
        last = datetime.fromtimestamp(m["last_at"] / 1000, timezone.utc).date().isoformat() if m["last_at"] else ""
        writer.writerow([_cell(m["name"]), m["sessions"], last, *[m["levels"].get(s["id"], "") for s in skills],
                         label.get(m["weakest"], "")])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=team-insights.csv"})
