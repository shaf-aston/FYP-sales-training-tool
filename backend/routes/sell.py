"""Sell mode endpoints (/api/sell): the learner is the salesperson, the AI (BuyerSession) buys."""

from flask import Blueprint, current_app, jsonify, request

from core.analytics.session_analytics import SessionAnalytics
from core.buyer_state import UnknownPersona, persona_name, personas_for
from core.constants import MAX_CHOSEN_OBJECTION_CHARS, MAX_PERSONA_NAME_CHARS
from core.drills import build_drill_set
from core.quiz import build_sell_question, score_sell_answer
from core.services.provider_router import ProviderUnavailable
from core import sell_service
from core.sell_service import InvalidDifficulty

from ..messages import (
    INVALID_DIFFICULTY,
    NO_TURNS_YET,
    OPTIONAL_TEXT_INVALID,
    SELL_ERROR,
    SELL_FULL,
    SELL_SETUP_FAILED,
    SELL_REVIEW_ERROR,
    SELL_SCORING_ERROR,
    SELL_UNAVAILABLE,
    SESSION_ENDED,
    TURN_NOT_IN_SESSION,
    TURN_REQUIRED,
    UNKNOWN_PERSONA,
)
from ..security import InputValidator, require_rate_limit
from ._utils import validate_message, validate_provider, with_session

bp = Blueprint("sell", __name__, url_prefix="/api/sell")


def _persona_card(persona: dict) -> dict:
    """What the web app shows about a buyer persona."""
    return {
        "name": persona_name(persona),
        "background": persona.get("background", ""),
        "personality": persona.get("personality", ""),
    }


def _unavailable():
    return jsonify({"error": SELL_UNAVAILABLE, "code": "PROVIDER_UNAVAILABLE"}), 503


def _live_buyer():
    """The caller's buyer session when a valid live id is sent, else None; or an error for a malformed id.

    For the routes that also work without a session.
    """
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        return None, None
    session_error = InputValidator.validate_session_id(session_id)
    if session_error:
        return None, session_error
    return current_app.extensions["sessions"].buyer.get(session_id), None


@bp.route("/personas", methods=["GET"])
def personas():
    """The buyer personas a learner can pick for one product."""
    product_type = request.args.get("product_type", "default")
    return jsonify({"success": True, "personas": [_persona_card(p) for p in personas_for(product_type)]})


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
        return None, (jsonify({"error": OPTIONAL_TEXT_INVALID.format(field=field, limit=limit)}), 400)
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
    chosen_persona, error = _optional_text(data, "persona", MAX_PERSONA_NAME_CHARS)
    if error:
        return error
    objection, error = _optional_text(data, "objection", MAX_CHOSEN_OBJECTION_CHARS)
    if error:
        return error

    product_type = data.get("product_type", "default")
    try:
        started = sell_service.start_sell_session(
            buyer_sessions,
            difficulty=data.get("difficulty"),
            product_type=product_type,
            provider=provider,
            persona_name=chosen_persona,
            objection=objection,
        )
    except InvalidDifficulty as e:
        return jsonify({"error": INVALID_DIFFICULTY.format(choices=", ".join(e.choices))}), 400
    except UnknownPersona as e:
        return jsonify({"error": UNKNOWN_PERSONA.format(name=e.name, product=e.product_type)}), 400
    except ProviderUnavailable:
        return _unavailable()
    except Exception as e:
        current_app.logger.exception(f"Sell init failed: {e}")
        return jsonify({"error": SELL_SETUP_FAILED}), 500

    buyer, opening = started.session, started.opening
    current_app.logger.info(
        f"Sell session: {buyer.session_id} "
        f"(difficulty={buyer.state.difficulty}, product={product_type}, provider={buyer.provider_name})"
    )
    return jsonify(
        {
            "success": True,
            "session_id": buyer.session_id,
            "message": opening.content,
            "persona": _persona_card(buyer.persona),
            "state": opening.state_snapshot,
            "difficulty": buyer.state.difficulty,
            "product_type": product_type,
            "latency_ms": opening.latency_ms,
            "provider": opening.provider,
            "model": opening.model,
        }
    )


@bp.route("/chat", methods=["POST"])
@require_rate_limit("sell")
@with_session("buyer")
def chat(buyer):
    """The learner sends a sales message; the AI buyer responds"""
    data = request.json or {}
    user_message, err = validate_message(data.get("message", ""))
    if err:
        return err

    if buyer.state.ended:
        return jsonify({"error": SESSION_ENDED}), 400

    try:
        response = buyer.process_turn(user_message, show_hints=data.get("show_hints", False))
        result = {
            "success": True,
            "message": response.content,
            "state": response.state_snapshot,
            "latency_ms": response.latency_ms,
            "provider": response.provider,
            "model": response.model,
            "ended": buyer.state.ended,
            "outcome": buyer.state.status,
        }
        if response.coaching:
            result["coaching"] = response.coaching
        return jsonify(result)
    except ProviderUnavailable:
        return _unavailable()
    except Exception as e:
        current_app.logger.exception(f"Sell chat error: {e}")
        return jsonify({"error": SELL_ERROR}), 500


@bp.route("/state", methods=["GET"])
@with_session("buyer")
def state(buyer):
    """Get current sell session state"""
    return jsonify(
        {
            "success": True,
            "state": buyer.state.to_dict(),
            "persona": buyer.persona,
            "difficulty": buyer.state.difficulty,
            "product_type": buyer.state.product_type,
            "conversation_history": buyer.conversation_history,
            "provider": buyer.provider_name,
            "model": buyer.model_name,
        }
    )


@bp.route("/evaluate", methods=["POST"])
@require_rate_limit("sell")
@with_session("buyer")
def evaluate(buyer):
    """Generate final evaluation scorecard"""
    try:
        evaluation = buyer.get_evaluation()
        SessionAnalytics.record(
            session_id=buyer.session_id,
            event="session_score",
            mode="sell",
            difficulty=buyer.state.difficulty,
            outcome=buyer.state.status,
            total=evaluation.get("overall_score"),
            grade=evaluation.get("grade"),
            breakdown={
                name: data.get("score")
                for name, data in (evaluation.get("criteria_scores") or {}).items()
            },
            turn_count=buyer.state.turn_count,
        )
        return jsonify({"success": True, **evaluation})
    except Exception as e:
        current_app.logger.exception(f"Sell evaluation error: {e}")
        return jsonify({"error": SELL_SCORING_ERROR}), 500


@bp.route("/review", methods=["GET"])
@require_rate_limit("sell")
@with_session("buyer")
def review(buyer):
    """Walk the session back turn by turn, with the reason behind every rating.

    Rebuilt from the transcript on each request, so it never drifts from what the learner saw.
    """
    try:
        return jsonify({"success": True, "persona": buyer.persona, **buyer.review()})
    except Exception as e:
        current_app.logger.exception(f"Sell review error: {e}")
        return jsonify({"error": SELL_REVIEW_ERROR}), 500


@bp.route("/quiz", methods=["GET"])
@require_rate_limit("sell")
@with_session("buyer")
def quiz_question(buyer):
    """A question about the learner's own weakest turn."""
    question = build_sell_question(buyer.review()["turns"])
    if question is None:
        return jsonify({"error": NO_TURNS_YET, "code": "NO_TURNS"}), 400
    return jsonify({"success": True, **question})


@bp.route("/quiz", methods=["POST"])
@require_rate_limit("sell")
@with_session("buyer")
def quiz_answer(buyer):
    """Score a replacement line for one of the learner's own turns."""
    data = request.json or {}
    turn_index = InputValidator.parse_positive_int(data.get("turn"))
    turns = buyer.review()["turns"]
    if turn_index is None or turn_index > len(turns):
        return jsonify({"error": TURN_NOT_IN_SESSION, "code": "INVALID_TURN"}), 400

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
    buyer, error = _live_buyer()
    if error:
        return error
    return jsonify({"success": True, **build_drill_set(buyer.review()["turns"] if buyer else [])})


@bp.route("/redo", methods=["POST"])
@require_rate_limit("sell")
@with_session("buyer")
def redo(buyer):
    """Rewind to a turn and say it differently, for a real reply from the same buyer."""
    data = request.json or {}
    turn_index = InputValidator.parse_positive_int(data.get("turn"))
    if turn_index is None:
        return jsonify({"error": TURN_REQUIRED, "code": "INVALID_TURN"}), 400

    user_message, err = validate_message(data.get("message", ""))
    if err:
        return err

    try:
        response = buyer.redo(turn_index, user_message)
        if response is None:
            return jsonify({"error": TURN_NOT_IN_SESSION, "code": "INVALID_TURN"}), 400
        return jsonify(
            {
                "success": True,
                "turn": turn_index,
                "message": response.content,
                "state": response.state_snapshot,
                "provider": response.provider,
                "model": response.model,
                "outcome": buyer.state.status,
            }
        )
    except ProviderUnavailable:
        return _unavailable()
    except Exception as e:
        current_app.logger.exception(f"Sell redo error: {e}")
        return jsonify({"error": SELL_ERROR}), 500


@bp.route("/reset", methods=["POST"])
@require_rate_limit("sell")
def reset():
    """End and remove a sell session; a missing or expired one is already gone."""
    buyer, error = _live_buyer()
    if error:
        return error
    if buyer is not None:
        buyer.record_session_end()
        current_app.extensions["sessions"].buyer.delete(buyer.session_id)
    return jsonify({"success": True})
