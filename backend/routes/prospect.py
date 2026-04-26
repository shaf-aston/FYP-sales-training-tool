"""Prospect mode endpoints - role-reversal where user plays salesperson"""

import secrets
from typing import Any, cast

from flask import Blueprint, jsonify, request

from ..messages import (
    PROSPECT_ERROR,
    PROSPECT_SCORING_ERROR,
    PROSPECT_SESSION_NOT_FOUND,
)
from ..security import InputValidator, require_rate_limit
from core.prospect_session_persistence import ProspectSessionPersistence
from core.providers.factory import supported_provider_names

bp = Blueprint("prospect", __name__, url_prefix="/api/prospect")


def _bp_state() -> Any:
    """Access blueprint-attached state through a typed escape hatch."""
    return cast(Any, bp)


def init_routes(app, prospect_session_manager_obj, validate_message_func):
    """Initialize prospect routes with Flask app and callback functions"""
    state = _bp_state()
    state.app = app
    state.prospect_session_manager = prospect_session_manager_obj
    state.validate_message = validate_message_func


def _public_config(ps: Any) -> dict:
    fn = getattr(ps, "public_config", None)
    if callable(fn):
        try:
            cfg = fn()
            return cfg if isinstance(cfg, dict) else {}
        except Exception:
            return {}
    return {}


def _require_prospect_session():
    """Validate prospect session. Returns (prospect_session, error_response)"""
    session_id = request.headers.get("X-Session-ID")
    session_error = InputValidator.validate_session_id(session_id)
    if session_error:
        return None, session_error
    assert isinstance(session_id, str)
    ps = _bp_state().prospect_session_manager.get(session_id)
    if not ps:
        return None, (
            jsonify({"error": PROSPECT_SESSION_NOT_FOUND, "code": "SESSION_EXPIRED"}),
            400,
        )
    return ps, None


@bp.route("/products", methods=["GET"])
def prospect_products():
    """Return product types that have prospect personas defined in prospect_config.yaml."""
    from core.loader import load_prospect_config, load_product_config

    personas = load_prospect_config().get("personas", {})
    products = load_product_config().get("products", {})

    result = []
    for persona_type, persona_list in personas.items():
        if persona_type == "general" or not persona_list:
            continue
        product_info = products.get(persona_type, {})
        result.append({
            "id": persona_type,
            "label": product_info.get("name") or persona_type.replace("_", " ").title(),
            "strategy": product_info.get("strategy", "consultative"),
        })

    return jsonify({"ok": True, "products": result})


@bp.route("/init", methods=["POST"])
@require_rate_limit("prospect")
def prospect_init():
    """Create a prospect session. Bot plays the buyer, user plays the salesperson"""
    state = _bp_state()
    if not state.prospect_session_manager.can_create():
        return jsonify(
            {"error": "Prospect mode is at capacity - check back in a moment."}
        ), 503

    data = request.json or {}
    difficulty = data.get("difficulty", "medium")
    product_type = data.get("product_type", "default")
    provider = InputValidator.normalize_provider(data.get("provider"))
    if provider is not None and provider not in supported_provider_names(include_non_production=False):
        return (
            jsonify(
                {
                    "error": "Unsupported provider",
                    "code": "UNSUPPORTED_PROVIDER",
                    "supported_providers": supported_provider_names(
                        include_non_production=False
                    ),
                }
            ),
            400,
        )

    if difficulty not in ("easy", "medium", "hard"):
        return jsonify({"error": "Invalid difficulty. Choose: easy, medium, hard"}), 400

    session_id = secrets.token_hex(16)

    try:
        from core.prospect_session import ProspectSession

        ps = ProspectSession(
            provider_type=provider,
            product_type=product_type,
            difficulty=difficulty,
            session_id=session_id,
        )
        opening = ps.get_opening_message()
        state.prospect_session_manager.set(session_id, ps)
        ps.save_session()
        state.app.logger.info(
            f"Prospect session: {session_id} "
            f"(difficulty={difficulty}, product={product_type}, provider={ps.provider_name})"
        )

        return jsonify(
            {
                "success": True,
                "session_id": session_id,
                "message": opening.content,
                "persona": {
                    "name": ps.persona.get("name", "Unknown"),
                    "background": ps.persona.get("background", ""),
                    "personality": ps.persona.get("personality", ""),
                },
                "state": opening.state_snapshot,
                "difficulty": difficulty,
                "product_type": product_type,
                **_public_config(ps),
                "latency_ms": opening.latency_ms,
                "provider": opening.provider,
                "model": opening.model,
            }
        )
    except Exception as e:
        state.app.logger.exception(f"Prospect init failed: {e}")
        return jsonify(
            {"error": "Couldn't set up the prospect session -- try once more"}
        ), 500


@bp.route("/chat", methods=["POST"])
@require_rate_limit("prospect")
def prospect_chat():
    """User sends a sales message; prospect responds"""
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None

    data = request.json or {}
    user_message, err = _bp_state().validate_message(data.get("message", ""))
    if err:
        return err

    if ps.state.has_committed or ps.state.has_walked:
        return jsonify({"error": "Session has ended. Get evaluation or reset."}), 400

    show_hints = data.get("show_hints", False)

    try:
        response = ps.process_turn(user_message, show_hints=show_hints)
        result = {
            "success": True,
            "message": response.content,
            "state": response.state_snapshot,
            "latency_ms": response.latency_ms,
            "provider": response.provider,
            "model": response.model,
            "ended": ps.state.has_committed or ps.state.has_walked,
            "outcome": ps.state.status,
        }
        if response.coaching:
            result["coaching"] = response.coaching
        return jsonify(result)
    except Exception as e:
        _bp_state().app.logger.exception(f"Prospect chat error: {e}")
        return jsonify({"error": PROSPECT_ERROR}), 500


@bp.route("/state", methods=["GET"])
def prospect_state():
    """Get current prospect session state"""
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None
    return jsonify(
        {
            "success": True,
            "state": ps.state.to_dict(),
            "persona": ps.persona,
            "difficulty": ps.state.difficulty,
            "product_type": ps.state.product_type,
            "conversation_history": ps.conversation_history,
            **_public_config(ps),
            "provider": ps.provider_name,
            "model": ps.model_name,
        }
    )


@bp.route("/evaluate", methods=["POST"])
@require_rate_limit("prospect")
def prospect_evaluate():
    """Generate final evaluation scorecard"""
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None

    try:
        evaluation = ps.get_evaluation()
        return jsonify({"success": True, **evaluation})
    except Exception as e:
        _bp_state().app.logger.exception(f"Prospect evaluation error: {e}")
        return jsonify({"error": PROSPECT_SCORING_ERROR}), 500


@bp.route("/reset", methods=["POST"])
@require_rate_limit("prospect")
def prospect_reset():
    """End and remove a prospect session"""
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        session_error = InputValidator.validate_session_id(session_id)
        if session_error:
            return session_error
        _bp_state().prospect_session_manager.delete(session_id)
        ProspectSessionPersistence.delete(session_id)
    return jsonify({"success": True})
