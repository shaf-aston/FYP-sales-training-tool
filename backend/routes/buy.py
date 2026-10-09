"""Buy mode endpoints (/api/buy): the learner is the customer, the AI (SellerBot) sells.

Session start and end, chat, edit, the coach's Q&A and the stage/move quiz.
"""

import logging

from flask import Blueprint, current_app, jsonify, request

from core.coach import COACH_STYLES, DEFAULT_STYLE
from core.constants import MAX_MESSAGE_LENGTH, MAX_SELLER_SESSIONS
from core.quiz import get_quiz_question
from core.seller_bot import SellerBot
from core.utils import new_session_id

from ..messages import (
    COACH_FAILED,
    EDIT_FAILED,
    FIELD_REQUIRED,
    GENERIC_ERROR,
    INVALID_INDEX,
    LABEL_TOO_LONG,
    MISSING_INDEX,
    QUESTION_REQUIRED,
    QUESTION_TOO_LONG,
    REWIND_FAILED,
    SELLER_INIT_FAILED,
    SERVER_FULL,
)
from ..security import InputValidator, require_rate_limit
from ._utils import (
    history_json,
    safe_latency_ms,
    stage_fields,
    validate_message,
    validate_provider,
    with_session,
)

logger = logging.getLogger(__name__)

bp = Blueprint("buy", __name__, url_prefix="/api/buy")


# --- session start and end ---


@bp.route("/init", methods=["POST"])
@require_rate_limit("buy_init")
def init():
    """Start a session (the seller is built now, so the first message doesn't wait), or reattach to a live one."""
    data = request.json or {}
    existing_id = data.get("session_id")
    sellers = current_app.extensions["sessions"].seller

    # Restore existing session only if it is still in memory on this process.
    if existing_id:
        session_error = InputValidator.validate_session_id(existing_id)
        if session_error:
            return session_error
        seller = sellers.get(existing_id)
        if seller:
            history = history_json(seller.call.conversation_history)
            current_app.logger.info(f"Restored session: {existing_id} ({len(history)} messages)")
            return jsonify(
                {
                    "success": True,
                    "session_id": existing_id,
                    "message": None,
                    **stage_fields(seller),
                    "history": history,
                }
            )

    if not sellers.can_create():
        current_app.logger.warning(f"Session cap ({MAX_SELLER_SESSIONS}) reached - rejecting new init")
        return jsonify({"error": SERVER_FULL}), 503

    session_id = new_session_id()
    product_type = data.get("product_type")  # unlisted or missing: script/engine.yaml default_product
    provider, provider_error = validate_provider(data)
    if provider_error:
        return provider_error

    try:
        seller = SellerBot(provider_type=provider, product_type=product_type, session_id=session_id)
        sellers.set(session_id, seller)
        current_app.logger.info(
            f"New session: {session_id} (product={seller.product_type}, provider={seller.provider_name})"
        )
    except Exception as init_error:
        current_app.logger.exception(f"Seller init failed: {init_error}")
        return jsonify({"error": SELLER_INIT_FAILED}), 500

    opening = seller.script_opening()
    seller.open_with(opening)

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "message": opening,
            **stage_fields(seller),
            "history": [],
            "training": seller.coach_notes(),  # the web app reads coach notes under this key
        }
    )


@bp.route("/reset", methods=["POST"])
@with_session("seller")
def reset(seller):
    """Delete the current session"""
    # Telemetry must never be the reason a learner cannot end their session.
    try:
        seller.record_session_end()
    except Exception:
        logger.exception("Could not record the end of this session")
    current_app.extensions["sessions"].seller.delete(request.headers.get("X-Session-ID"))
    return jsonify({"success": True})


# --- the conversation ---


@bp.route("/chat", methods=["POST"])
@require_rate_limit("buy_chat")
@with_session("seller")
def chat(seller):
    """The learner's message; the AI seller answers."""
    data = request.get_json(silent=True) or {}
    user_message, error = validate_message(data.get("message", ""))
    if error:
        return error

    try:
        response = seller.chat(user_message)
        return jsonify(
            {
                "success": True,
                "message": response.content,
                **stage_fields(seller),
                "latency_ms": safe_latency_ms(response.latency_ms),
                "provider": response.provider,
                "model": response.model,
                "metrics": {
                    "input_length": response.input_len,
                    "output_length": response.output_len,
                },
                "training": seller.coach_notes(),
            }
        )
    except Exception as e:
        current_app.logger.exception(f"Chat error: {e}")
        return jsonify({"error": GENERIC_ERROR}), 500


@bp.route("/edit", methods=["POST"])
@require_rate_limit("buy_chat")
@with_session("seller")
def edit(seller):
    """Edit a learner message and replay the call from there."""
    data = request.json or {}
    message_index = data.get("index")
    new_message, error = validate_message(data.get("message", ""))
    if error:
        return error

    if message_index is None:
        return jsonify({"error": MISSING_INDEX}), 400
    try:
        message_index = int(message_index)
    except (TypeError, ValueError):
        return jsonify({"error": INVALID_INDEX}), 400

    try:
        response = seller.edit_turn(message_index, new_message)
        if response is None:
            return jsonify({"error": REWIND_FAILED}), 500
        return jsonify(
            {
                "success": True,
                "message": response.content,
                "history": history_json(seller.call.conversation_history),
                **stage_fields(seller),
                "latency_ms": safe_latency_ms(response.latency_ms),
                "provider": response.provider,
                "model": response.model,
                "training": seller.coach_notes(),
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception(f"Edit error: {e}")
        return jsonify({"error": EDIT_FAILED}), 500


@bp.route("/coach", methods=["POST"])
@require_rate_limit("buy_chat")
@with_session("seller")
def coach(seller):
    """Answer the learner's question about the call and sales technique."""
    data = request.json or {}
    question = (data.get("question") or "").strip()
    style = (data.get("style") or DEFAULT_STYLE).strip().lower()
    if style not in COACH_STYLES:
        style = DEFAULT_STYLE
    if not question:
        return jsonify({"error": QUESTION_REQUIRED}), 400
    if len(question) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": QUESTION_TOO_LONG}), 400

    try:
        return jsonify({"success": True, **seller.answer_coach_question(question, style=style)})
    except Exception as e:
        current_app.logger.exception(f"Coach answer error: {e}")
        return jsonify({"error": COACH_FAILED}), 500


# --- quiz: where is the AI seller in its script, and what should it do next ---


@bp.route("/quiz/question", methods=["GET"])
@with_session("seller")
def quiz_question(seller):
    """A random question for the quiz type in ?type= (stage, next-move, direction)."""
    quiz_type = request.args.get("type", "stage")
    return jsonify(
        {
            "success": True,
            "question": get_quiz_question(quiz_type),
            "type": quiz_type,
            **stage_fields(seller),
        }
    )


def _required_text(field: str, label: str):
    """A stripped required text field from the JSON body, or an error response."""
    value = ((request.json or {}).get(field) or "").strip()
    if not value:
        return None, (jsonify({"error": FIELD_REQUIRED.format(label=label)}), 400)
    if len(value) > MAX_MESSAGE_LENGTH:
        return None, (jsonify({"error": LABEL_TOO_LONG.format(label=label)}), 400)
    return value, None


@bp.route("/quiz/stage", methods=["POST"])
@with_session("seller")
def quiz_stage(seller):
    """Stage identification quiz (scored by rule)."""
    answer, error = _required_text("answer", "Answer")
    if error:
        return error
    return jsonify({"success": True, **seller.score_stage_answer(answer), **stage_fields(seller)})


@bp.route("/quiz/next-move", methods=["POST"])
@with_session("seller")
def quiz_next_move(seller):
    """Next move quiz (rules score it, the AI may add wording)."""
    response, error = _required_text("response", "Response")
    if error:
        return error
    return jsonify({"success": True, **seller.score_next_move(response), **stage_fields(seller)})


@bp.route("/quiz/direction", methods=["POST"])
@with_session("seller")
def quiz_direction(seller):
    """Direction quiz (rules score it, the AI may add wording)."""
    explanation, error = _required_text("explanation", "Explanation")
    if error:
        return error
    return jsonify({"success": True, **seller.score_direction(explanation), **stage_fields(seller)})
