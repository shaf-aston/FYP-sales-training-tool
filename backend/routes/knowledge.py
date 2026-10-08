"""Custom product knowledge endpoints (/api/knowledge), shared by both modes."""

from flask import Blueprint, jsonify, request

from core.knowledge import (
    ALLOWED_FIELDS,
    MAX_FIELD_LENGTH,
    clear_custom_knowledge,
    load_custom_knowledge,
    save_custom_knowledge,
)

from ..messages import INVALID_PAYLOAD
from ..security import InputValidator, require_rate_limit

bp = Blueprint("knowledge", __name__, url_prefix="/api")


@bp.route("/knowledge", methods=["GET"])
@require_rate_limit("knowledge")
def get_knowledge():
    """Retrieve current custom knowledge"""
    return jsonify({"success": True, "data": load_custom_knowledge()})


@bp.route("/knowledge", methods=["POST"])
@require_rate_limit("knowledge")
def save_knowledge_route():
    """Save custom knowledge data with field-level validation"""
    data = request.json or {}
    if not isinstance(data, dict):
        return jsonify({"error": INVALID_PAYLOAD}), 400

    error = InputValidator.validate_knowledge_data(
        data, allowed_fields=ALLOWED_FIELDS, max_field_length=MAX_FIELD_LENGTH
    )
    if error:
        return error

    success = save_custom_knowledge(data)
    return jsonify({"success": success})


@bp.route("/knowledge", methods=["DELETE"])
@require_rate_limit("knowledge")
def clear_knowledge_route():
    """Clear all custom knowledge"""
    success = clear_custom_knowledge()
    return jsonify({"success": success})
