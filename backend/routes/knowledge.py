"""A learner's product details for the sell-mode buyer (/api/knowledge), kept on their account.

Signed out, the web keeps them in the browser instead; either way they come with each new sell call
(/api/sell/init `knowledge`). There is no shared copy: one learner's details never reach another's buyer.
"""

from flask import Blueprint, jsonify, request

from core.accounts.db import database
from core.accounts.library import Library
from core.infra.constants import MAX_FIELD_LENGTH
from core.sell_mode.knowledge import ALLOWED_FIELDS, sanitise_knowledge

from ..auth import require_user
from ..messages import INVALID_PAYLOAD
from ..security import InputValidator, require_rate_limit

bp = Blueprint("knowledge", __name__, url_prefix="/api")


@bp.route("/knowledge", methods=["GET"])
@require_rate_limit("knowledge")
@require_user
def get_knowledge(user):
    return jsonify({"success": True, "data": Library(database()).knowledge(user.id)})


@bp.route("/knowledge", methods=["POST"])
@require_rate_limit("knowledge")
@require_user
def save_knowledge_route(user):
    """Save the details, checked field by field."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": INVALID_PAYLOAD}), 400
    error = InputValidator.validate_knowledge_data(data, allowed_fields=ALLOWED_FIELDS, max_field_length=MAX_FIELD_LENGTH)
    if error:
        return error
    cleaned = sanitise_knowledge(data)
    Library(database()).save_knowledge(user.id, cleaned)
    return jsonify({"success": True, "data": cleaned})


@bp.route("/knowledge", methods=["DELETE"])
@require_rate_limit("knowledge")
@require_user
def clear_knowledge_route(user):
    Library(database()).save_knowledge(user.id, {})
    return jsonify({"success": True})
