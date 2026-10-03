"""Prospect mode endpoints - role-reversal where user plays salesperson"""

import secrets
from typing import Any, cast

from flask import Blueprint, jsonify, request

from ..messages import (
    PROSPECT_ERROR,
    PROSPECT_REVIEW_ERROR,
    PROSPECT_UNAVAILABLE,
    PROSPECT_SCORING_ERROR,
    PROSPECT_SESSION_NOT_FOUND,
)
from ..security import InputValidator, require_rate_limit
from ._utils import make_require_session, validate_provider
from core.analytics.session_analytics import SessionAnalytics
from core.constants import MAX_CHOSEN_OBJECTION_CHARS, MAX_PERSONA_NAME_CHARS
from core.prospect_session import ProviderUnavailable
from core.quiz import build_prospect_question, score_prospect_answer
from core.script_drills import build_drill_set

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


def _lookup_prospect_session(session_id):
    """Return the live prospect session for this id, or None."""
    return _bp_state().prospect_session_manager.get(session_id)


_require_prospect_session = make_require_session(
    _lookup_prospect_session, PROSPECT_SESSION_NOT_FOUND
)


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


@bp.route("/personas", methods=["GET"])
def prospect_personas():
    """The buyer personas a learner can pick for one product."""
    from core.prospect_session import personas_for

    product_type = request.args.get("product_type", "default")
    return jsonify({
        "ok": True,
        "personas": [
            {"name": p["name"], "background": p.get("background", ""), "personality": p.get("personality", "")}
            for p in personas_for(product_type)
        ],
    })


def _optional_text(data: dict, field: str, limit: int):
    """A stripped optional string field, or an error response when it is the wrong shape."""
    value = data.get(field)
    if value in (None, ""):
        return None, None
    if not isinstance(value, str) or len(value.strip()) > limit:
        return None, (jsonify({"error": f"{field} must be text up to {limit} characters"}), 400)
    return value.strip() or None, None


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
    provider, provider_error = validate_provider(data)
    if provider_error:
        return provider_error

    if difficulty not in ("easy", "medium", "hard"):
        return jsonify({"error": "Invalid difficulty. Choose: easy, medium, hard"}), 400
    persona_name, error = _optional_text(data, "persona", MAX_PERSONA_NAME_CHARS)
    if error:
        return error
    objection, error = _optional_text(data, "objection", MAX_CHOSEN_OBJECTION_CHARS)
    if error:
        return error

    from core.prospect_session import ProspectSession, select_persona

    try:
        persona = select_persona(product_type, persona_name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session_id = secrets.token_hex(16)

    try:
        ps = ProspectSession(
            provider_type=provider,
            product_type=product_type,
            difficulty=difficulty,
            persona=persona,
            session_id=session_id,
            objection=objection,
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
                **ps.public_config(),
                "latency_ms": opening.latency_ms,
                "provider": opening.provider,
                "model": opening.model,
            }
        )
    except ProviderUnavailable:
        state.prospect_session_manager.delete(session_id)
        return jsonify({"error": PROSPECT_UNAVAILABLE, "code": "PROVIDER_UNAVAILABLE"}), 503
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
    except ProviderUnavailable:
        return jsonify({"error": PROSPECT_UNAVAILABLE, "code": "PROVIDER_UNAVAILABLE"}), 503
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
            **ps.public_config(),
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
        SessionAnalytics.record(
            session_id=request.headers.get("X-Session-ID", ""),
            event="session_score",
            engine="prospect",
            difficulty=ps.state.difficulty,
            outcome=ps.state.status,
            total=evaluation.get("overall_score"),
            grade=evaluation.get("grade"),
            breakdown={
                name: data.get("score")
                for name, data in (evaluation.get("criteria_scores") or {}).items()
            },
            turn_count=ps.state.turn_count,
        )
        return jsonify({"success": True, **evaluation})
    except Exception as e:
        _bp_state().app.logger.exception(f"Prospect evaluation error: {e}")
        return jsonify({"error": PROSPECT_SCORING_ERROR}), 500


@bp.route("/review", methods=["GET"])
@require_rate_limit("prospect")
def prospect_review():
    """Walk the session back turn by turn, with the reason behind every rating.

    Rebuilt from the transcript on each request, so it also works on a session
    that was recovered from disk.
    """
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None

    try:
        return jsonify({"success": True, "persona": ps.persona, **ps.review()})
    except Exception as e:
        _bp_state().app.logger.exception(f"Prospect review error: {e}")
        return jsonify({"error": PROSPECT_REVIEW_ERROR}), 500


@bp.route("/quiz", methods=["GET"])
@require_rate_limit("prospect")
def prospect_quiz_question():
    """A question about the learner's own weakest turn, not the AI salesperson's flow."""
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None

    question = build_prospect_question(ps.review()["turns"])
    if question is None:
        return jsonify({"error": "Say a few things to the buyer first - the quiz uses your own turns.", "code": "NO_TURNS"}), 400
    return jsonify({"success": True, **question})


@bp.route("/quiz", methods=["POST"])
@require_rate_limit("prospect")
def prospect_quiz_answer():
    """Score a replacement line for one of the learner's own turns."""
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None

    data = request.json or {}
    turn_index = InputValidator.parse_positive_int(data.get("turn"))
    turns = ps.review()["turns"]
    if turn_index is None or turn_index > len(turns):
        return jsonify({"error": "That turn is not part of this session.", "code": "INVALID_TURN"}), 400

    answer, err = _bp_state().validate_message(data.get("answer", ""))
    if err:
        return err

    return jsonify({"success": True, **score_prospect_answer(answer, turns[turn_index - 1])})


@bp.route("/drills", methods=["GET"])
@require_rate_limit("prospect")
def prospect_drills():
    """Lines to recall, with the move blanked out.

    Works with no session at all. When a live session is supplied, that learner's
    own strongest turns are added at the top - revising something you actually
    said beats revising a stranger's script.
    """
    own_turns = []
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        session_error = InputValidator.validate_session_id(session_id)
        if session_error:
            return session_error
        ps = _lookup_prospect_session(session_id)
        if ps is not None:
            own_turns = ps.review()["turns"]

    return jsonify({"success": True, **build_drill_set(own_turns)})


def _restore_after_failed_redo(ps, kept_history, kept_state):
    """Put the turns back when the redo never reached the buyer.

    Rewinding happens before the buyer is asked, so a failure here would otherwise
    cost the learner every turn after the one they were redoing, and give them
    nothing in return.
    """
    ps.conversation_history = kept_history
    (
        ps.state.turn_count,
        ps.state.readiness,
        ps.state.objections_raised,
        ps.state.has_committed,
        ps.state.has_walked,
    ) = kept_state


@bp.route("/redo", methods=["POST"])
@require_rate_limit("prospect")
def prospect_redo():
    """Rewind to a turn and say it differently, for a real reply from the same buyer."""
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None

    data = request.json or {}
    turn_index = InputValidator.parse_positive_int(data.get("turn"))
    if turn_index is None:
        return jsonify({"error": "A turn number is required.", "code": "INVALID_TURN"}), 400

    user_message, err = _bp_state().validate_message(data.get("message", ""))
    if err:
        return err

    kept_history = list(ps.conversation_history)
    kept_state = (
        ps.state.turn_count,
        ps.state.readiness,
        ps.state.objections_raised,
        ps.state.has_committed,
        ps.state.has_walked,
    )
    if not ps.rewind_to_turn(turn_index):
        return jsonify({"error": "That turn is not part of this session.", "code": "INVALID_TURN"}), 400

    try:
        response = ps.process_turn(user_message)
        return jsonify(
            {
                "success": True,
                "turn": turn_index,
                "message": response.content,
                "state": response.state_snapshot,
                "provider": response.provider,
                "model": response.model,
                "outcome": ps.state.status,
            }
        )
    except ProviderUnavailable:
        _restore_after_failed_redo(ps, kept_history, kept_state)
        return jsonify({"error": PROSPECT_UNAVAILABLE, "code": "PROVIDER_UNAVAILABLE"}), 503
    except Exception as e:
        _restore_after_failed_redo(ps, kept_history, kept_state)
        _bp_state().app.logger.exception(f"Prospect redo error: {e}")
        return jsonify({"error": PROSPECT_ERROR}), 500


@bp.route("/reset", methods=["POST"])
@require_rate_limit("prospect")
def prospect_reset():
    """End and remove a prospect session"""
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        session_error = InputValidator.validate_session_id(session_id)
        if session_error:
            return session_error
        ps = _lookup_prospect_session(session_id)
        if ps is not None:
            ps.record_session_end()
        _bp_state().prospect_session_manager.delete(session_id)
    return jsonify({"success": True})
