"""Sell mode endpoints (/api/sell): the learner is the salesperson, the AI (BuyerSession) buys."""

import secrets

from flask import Blueprint, current_app, jsonify, request

from core.analytics.session_analytics import SessionAnalytics
from core.buyer_session import ProviderUnavailable
from core.constants import MAX_CHOSEN_OBJECTION_CHARS, MAX_PERSONA_NAME_CHARS
from core.quiz import build_sell_question, score_sell_answer
from core.script_drills import build_drill_set

from ..messages import (
    SELL_ERROR,
    SELL_REVIEW_ERROR,
    SELL_SCORING_ERROR,
    SELL_SESSION_NOT_FOUND,
    SELL_UNAVAILABLE,
)
from ..security import InputValidator, require_rate_limit
from ._utils import require_session, validate_message, validate_provider

bp = Blueprint("sell", __name__, url_prefix="/api/sell")


@bp.route("/personas", methods=["GET"])
def personas():
    """The buyer personas a learner can pick for one product."""
    from core.buyer_session import personas_for

    product_type = request.args.get("product_type", "default")
    return jsonify({
        "ok": True,
        "personas": [
            {"name": p["name"], "background": p.get("background", ""), "personality": p.get("personality", "")}
            for p in personas_for(product_type)
        ],
    })


# The products offered in the sell-mode picker, split by sales motion.
_PRODUCT_GROUPS = {
    "transactional": [
        "luxury_cars",
        "premium_electronics",
        "watches",
        "travel",
        "fashion",
    ],
    "consultative": [
        "b2b_saas",
        "high_ticket_sales_mentorship",
        "financial_services",
        "education",
        "healthcare_services",
    ],
}


def _product_groups() -> dict:
    """Curated picker groups; a product with no buyer personas is left out."""
    try:
        from core.loader import load_product_config, load_sell_config

        personas = load_sell_config().get("personas", {})
        products = load_product_config().get("products", {})

        grouped_options = {}
        for strategy, product_ids in _PRODUCT_GROUPS.items():
            options = []
            for product_id in product_ids:
                if not personas.get(product_id):
                    continue
                product_info = products.get(product_id, {})
                options.append(
                    {
                        "id": product_id,
                        "label": product_info.get("name")
                        or product_id.replace("_", " ").title(),
                    }
                )
            grouped_options[strategy] = options
        return grouped_options
    except Exception:
        current_app.logger.exception("Failed to build sell product groups")
        return {strategy: [] for strategy in _PRODUCT_GROUPS}


@bp.route("/product-groups", methods=["GET"])
def product_groups():
    """Curated product picker groups as JSON."""
    return jsonify({"success": True, "groups": _product_groups()})


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
    if not current_app.extensions["sessions"].buyer.can_create():
        return jsonify(
            {"error": "Sell mode is at capacity - check back in a moment."}
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

    from core.buyer_session import BuyerSession, select_persona

    try:
        persona = select_persona(product_type, persona_name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session_id = secrets.token_hex(16)

    try:
        ps = BuyerSession(
            provider_type=provider,
            product_type=product_type,
            difficulty=difficulty,
            persona=persona,
            session_id=session_id,
            objection=objection,
        )
        opening = ps.get_opening_message()
        current_app.extensions["sessions"].buyer.set(session_id, ps)
        ps.save_session()
        current_app.logger.info(
            f"Sell session: {session_id} "
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
        current_app.extensions["sessions"].buyer.delete(session_id)
        return jsonify({"error": SELL_UNAVAILABLE, "code": "PROVIDER_UNAVAILABLE"}), 503
    except Exception as e:
        current_app.logger.exception(f"Sell init failed: {e}")
        return jsonify(
            {"error": "Couldn't set up the buyer -- try once more"}
        ), 500


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
