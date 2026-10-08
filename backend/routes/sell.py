"""Sell mode endpoints (/api/sell): the learner is the salesperson, the AI (BuyerSession) buys."""

from flask import Blueprint, current_app, jsonify, request

from core.analytics.session_analytics import SessionAnalytics
from core.buyer_state import UnknownPersona, personas_for
from core.constants import MAX_CHOSEN_OBJECTION_CHARS, MAX_PERSONA_NAME_CHARS
from core.quiz import build_sell_question, score_sell_answer
from core.script_drills import build_drill_set
from core.services.provider_router import ProviderUnavailable
from core import sell_service
from core.sell_service import InvalidDifficulty

from ..messages import (
    INVALID_DIFFICULTY,
    SELL_ERROR,
    SELL_FULL,
    SELL_SETUP_FAILED,
    SELL_REVIEW_ERROR,
    SELL_SCORING_ERROR,
    SELL_SESSION_NOT_FOUND,
    SELL_UNAVAILABLE,
    UNKNOWN_PERSONA,
)
from ..security import InputValidator, require_rate_limit
from ._utils import require_session, validate_message, validate_provider

bp = Blueprint("sell", __name__, url_prefix="/api/sell")


@bp.route("/personas", methods=["GET"])
def personas():
    """The buyer personas a learner can pick for one product."""
    product_type = request.args.get("product_type", "default")
    return jsonify({
        "success": True,
        "personas": [
            {"name": p["name"], "background": p.get("background", ""), "personality": p.get("personality", "")}
            for p in personas_for(product_type)
        ],
    })


@bp.route("/product-groups", methods=["GET"])
def product_groups():
    """Curated product picker groups as JSON."""
    return jsonify({"success": True, "groups": sell_service.product_groups()})


def _optional_text(data: dict, field: str, limit: int):
    """A stripped optional string field, or an error response when it is the wrong shape."""
    value = data.get(field)
    if value in (None, ""):
        return None, None
    if not isinstance(value, str) or len(value.strip()) > limit:
        return None, (jsonify({"error": f"{field} must be text up to {limit} characters"}), 400)
    return value.strip() or None, None


@bp.route("/init", methods=["POST"])
@require_rate_limit("sell")
def init():
    """Create a sell session. The AI plays the buyer, the learner plays the salesperson"""
    buyer_sessions = current_app.extensions["sessions"].buyer
    if not buyer_sessions.can_create():
        return jsonify({"error": SELL_FULL}), 503

    data = request.json or {}
    provider, provider_error = validate_provider(data)
    if provider_error:
        return provider_error
    persona_name, error = _optional_text(data, "persona", MAX_PERSONA_NAME_CHARS)
    if error:
        return error
    objection, error = _optional_text(data, "objection", MAX_CHOSEN_OBJECTION_CHARS)
    if error:
        return error

    difficulty = data.get("difficulty", "medium")
    product_type = data.get("product_type", "default")
    try:
        started = sell_service.start_sell_session(
            buyer_sessions,
            difficulty=difficulty,
            product_type=product_type,
            provider=provider,
            persona_name=persona_name,
            objection=objection,
        )
    except InvalidDifficulty as e:
        return jsonify({"error": INVALID_DIFFICULTY.format(choices=", ".join(e.choices))}), 400
    except UnknownPersona as e:
        return jsonify({"error": UNKNOWN_PERSONA.format(name=e.name, product=e.product_type)}), 400
    except ProviderUnavailable:
        return jsonify({"error": SELL_UNAVAILABLE, "code": "PROVIDER_UNAVAILABLE"}), 503
    except Exception as e:
        current_app.logger.exception(f"Sell init failed: {e}")
        return jsonify({"error": SELL_SETUP_FAILED}), 500

    ps, opening = started.session, started.opening
    current_app.logger.info(
        f"Sell session: {ps.session_id} "
        f"(difficulty={difficulty}, product={product_type}, provider={ps.provider_name})"
    )
    return jsonify(
        {
            "success": True,
            "session_id": ps.session_id,
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


@bp.route("/chat", methods=["POST"])
@require_rate_limit("sell")
def chat():
    """The learner sends a sales message; the AI buyer responds"""
    ps, err = require_session("buyer", SELL_SESSION_NOT_FOUND)
    if err:
        return err
    assert ps is not None

    data = request.json or {}
    user_message, err = validate_message(data.get("message", ""))
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
        return jsonify({"error": SELL_UNAVAILABLE, "code": "PROVIDER_UNAVAILABLE"}), 503
    except Exception as e:
        current_app.logger.exception(f"Sell chat error: {e}")
        return jsonify({"error": SELL_ERROR}), 500


@bp.route("/state", methods=["GET"])
def state():
    """Get current sell session state"""
    ps, err = require_session("buyer", SELL_SESSION_NOT_FOUND)
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
@require_rate_limit("sell")
def evaluate():
    """Generate final evaluation scorecard"""
    ps, err = require_session("buyer", SELL_SESSION_NOT_FOUND)
    if err:
        return err
    assert ps is not None

    try:
        evaluation = ps.get_evaluation()
        SessionAnalytics.record(
            session_id=request.headers.get("X-Session-ID", ""),
            event="session_score",
            engine="sell",
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
        current_app.logger.exception(f"Sell evaluation error: {e}")
        return jsonify({"error": SELL_SCORING_ERROR}), 500


@bp.route("/review", methods=["GET"])
@require_rate_limit("sell")
def review():
    """Walk the session back turn by turn, with the reason behind every rating.

    Rebuilt from the transcript on each request, so it also works on a session
    that was recovered from disk.
    """
    ps, err = require_session("buyer", SELL_SESSION_NOT_FOUND)
    if err:
        return err
    assert ps is not None

    try:
        return jsonify({"success": True, "persona": ps.persona, **ps.review()})
    except Exception as e:
        current_app.logger.exception(f"Sell review error: {e}")
        return jsonify({"error": SELL_REVIEW_ERROR}), 500


@bp.route("/quiz", methods=["GET"])
@require_rate_limit("sell")
def quiz_question():
    """A question about the learner's own weakest turn, not the AI salesperson's flow."""
    ps, err = require_session("buyer", SELL_SESSION_NOT_FOUND)
    if err:
        return err
    assert ps is not None

    question = build_sell_question(ps.review()["turns"])
    if question is None:
        return jsonify({"error": "Say a few things to the buyer first - the quiz uses your own turns.", "code": "NO_TURNS"}), 400
    return jsonify({"success": True, **question})


@bp.route("/quiz", methods=["POST"])
@require_rate_limit("sell")
def quiz_answer():
    """Score a replacement line for one of the learner's own turns."""
    ps, err = require_session("buyer", SELL_SESSION_NOT_FOUND)
    if err:
        return err
    assert ps is not None

    data = request.json or {}
    turn_index = InputValidator.parse_positive_int(data.get("turn"))
    turns = ps.review()["turns"]
    if turn_index is None or turn_index > len(turns):
        return jsonify({"error": "That turn is not part of this session.", "code": "INVALID_TURN"}), 400

    answer, err = validate_message(data.get("answer", ""))
    if err:
        return err

    return jsonify({"success": True, **score_sell_answer(answer, turns[turn_index - 1])})


@bp.route("/drills", methods=["GET"])
@require_rate_limit("sell")
def drills():
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
        ps = current_app.extensions["sessions"].buyer.get(session_id)
        if ps is not None:
            own_turns = ps.review()["turns"]

    return jsonify({"success": True, **build_drill_set(own_turns)})


@bp.route("/redo", methods=["POST"])
@require_rate_limit("sell")
def redo():
    """Rewind to a turn and say it differently, for a real reply from the same buyer."""
    ps, err = require_session("buyer", SELL_SESSION_NOT_FOUND)
    if err:
        return err
    assert ps is not None

    data = request.json or {}
    turn_index = InputValidator.parse_positive_int(data.get("turn"))
    if turn_index is None:
        return jsonify({"error": "A turn number is required.", "code": "INVALID_TURN"}), 400

    user_message, err = validate_message(data.get("message", ""))
    if err:
        return err

    try:
        response = ps.redo(turn_index, user_message)
        if response is None:
            return jsonify({"error": "That turn is not part of this session.", "code": "INVALID_TURN"}), 400
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
        return jsonify({"error": SELL_UNAVAILABLE, "code": "PROVIDER_UNAVAILABLE"}), 503
    except Exception as e:
        current_app.logger.exception(f"Sell redo error: {e}")
        return jsonify({"error": SELL_ERROR}), 500


@bp.route("/reset", methods=["POST"])
@require_rate_limit("sell")
def reset():
    """End and remove a sell session"""
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        session_error = InputValidator.validate_session_id(session_id)
        if session_error:
            return session_error
        ps = current_app.extensions["sessions"].buyer.get(session_id)
        if ps is not None:
            ps.record_session_end()
        current_app.extensions["sessions"].buyer.delete(session_id)
    return jsonify({"success": True})
