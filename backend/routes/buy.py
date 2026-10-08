"""Buy mode endpoints (/api/buy): the learner is the customer, the AI (SellerBot) sells.

Session start and end, chat, edit, the coach's Q&A and the stage/move quiz.
"""

import logging
import secrets

from flask import Blueprint, current_app, jsonify, request

from core.constants import MAX_MESSAGE_LENGTH, MAX_SESSIONS
from core.quiz import get_quiz_question
from core.seller_bot import SellerBot

from ..messages import BOT_INIT_FAILED, GENERIC_ERROR, SERVER_FULL
from ..security import InputValidator, require_rate_limit
from ._utils import (
    bot_state,
    require_session,
    safe_latency_ms,
    validate_message,
    validate_provider,
    with_session,
)

logger = logging.getLogger(__name__)

bp = Blueprint("buy", __name__, url_prefix="/api/buy")


# --- session start and end ---


@bp.route("/init", methods=["POST"])
@require_rate_limit("init")
def init():
    """Initialize or restore an in-memory session. Creates bot eagerly to avoid first-message latency."""
    data = request.json or {}
    existing_id = data.get("session_id")

    # Restore existing session only if it is still in memory on this process.
    if existing_id:
        session_error = InputValidator.validate_session_id(existing_id)
        if session_error:
            return session_error
        bot = current_app.extensions["sessions"].seller.get(existing_id)
        if bot:
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in bot.flow_engine.conversation_history
            ]
            current_app.logger.info(
                f"Restored session: {existing_id} ({len(history)} messages)"
            )
            return jsonify(
                {
                    "success": True,
                    "session_id": existing_id,
                    "message": None,
                    **bot_state(bot),
                    "history": history,
                }
            )

    # Session count ceiling: reject new sessions when server is full
    if not current_app.extensions["sessions"].seller.can_create():
        current_app.logger.warning(
            f"Session cap ({MAX_SESSIONS}) reached - rejecting new init"
        )
        return jsonify(
            {"error": SERVER_FULL}
        ), 503

    # Create new session with eager bot initialization
    session_id = secrets.token_hex(16)
    product_type = data.get("product_type")  # unlisted or missing → selling.yaml default_product
    provider, provider_error = validate_provider(data)
    if provider_error:
        return provider_error

    try:
        bot = SellerBot(
            provider_type=provider, product_type=product_type, session_id=session_id
        )
        current_app.extensions["sessions"].seller.set(session_id, bot)
        bot.save_session()  # log the initial state snapshot for monitoring
        active_provider = getattr(bot, "provider_name", provider or "auto")
        current_app.logger.info(
            f"New session: {session_id} "
            f"(product={bot.product_type}, provider={active_provider})"
        )
    except Exception as init_error:
        current_app.logger.exception(f"Bot init failed: {init_error}")
        return jsonify(
            {"error": BOT_INIT_FAILED}
        ), 500

    opening = bot.script_opening()
    bot.open_with(opening)

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "message": opening,
            **bot_state(bot),
            "history": [],
            "training": bot.generate_training("", opening),
        }
    )


@bp.route("/reset", methods=["POST"])
@with_session
def reset(bot):
    """Delete the current session"""
    # Telemetry must never be the reason a learner cannot end their session.
    try:
        bot.record_session_end()
    except Exception:
        logger.exception("Could not record the end of this session")
    current_app.extensions["sessions"].seller.delete(request.headers.get("X-Session-ID"))
    return jsonify({"success": True})


# --- the conversation ---


@bp.route("/chat", methods=["POST"])
@require_rate_limit("chat")
def chat():
    """Handle chat messages. Bot must be initialized via /api/buy/init first"""

    data = request.get_json(silent=True) or {}
    user_message, error = validate_message(data.get("message", ""))
    if error:
        return error

    session_bot, error = require_session()
    if error:
        return error

    try:
        response = session_bot.chat(user_message)
        training = session_bot.generate_training(user_message, response.content)

        # Extract content and metrics from ChatResponse
        return jsonify(
            {
                "success": True,
                "message": response.content,
                **bot_state(session_bot),
                "latency_ms": safe_latency_ms(response.latency_ms),
                "provider": response.provider,
                "model": response.model,
                "metrics": {
                    "input_length": response.input_len,
                    "output_length": response.output_len,
                },
                "training": training,
            }
        )

    except Exception as e:
        current_app.logger.exception(f"Chat error: {e}")
        return jsonify({"error": GENERIC_ERROR}), 500


@bp.route("/edit", methods=["POST"])
@require_rate_limit("chat")
def edit():
    """Edit user message and regenerate from that point"""
    data = request.json or {}
    message_index = data.get("index")
    new_message, error = validate_message(data.get("message", ""))
    if error:
        return error

    session_bot, error = require_session()
    if error:
        return error

    # Validate inputs
    if message_index is None:
        return jsonify({"error": "Missing message index"}), 400

    try:
        message_index = int(message_index)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid index format"}), 400

    try:
        response = session_bot.edit_turn(message_index, new_message)
        if response is None:
            return jsonify({"error": "Rewind failed"}), 500
        training = session_bot.generate_training(new_message, response.content)

        return jsonify(
            {
                "success": True,
                "message": response.content,
                "history": [
                    {"role": message["role"], "content": message["content"]}
                    for message in session_bot.flow_engine.conversation_history
                ],
                **bot_state(session_bot),
                "latency_ms": safe_latency_ms(response.latency_ms),
                "provider": response.provider,
                "model": response.model,
                "training": training,
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception(f"Edit error: {e}")
        return jsonify({"error": "Couldn't apply that edit -- try again in a sec"}), 500


@bp.route("/coach", methods=["POST"])
@require_rate_limit("chat")
def coach():
    """Answer a trainee's question about the conversation and sales techniques"""
    session_bot, error = require_session()
    if error:
        return error

    data = request.json or {}
    question = (data.get("question") or "").strip()
    style = (data.get("style") or "tactical").strip().lower()
    if style not in ("tactical", "socratic", "teacher"):
        style = "tactical"
    if not question:
        return jsonify({"error": "Question required"}), 400
    if len(question) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Question too long"}), 400

    try:
        result = session_bot.answer_training_question(question, style=style)
        return jsonify({"success": True, **result})
    except Exception as e:
        current_app.logger.exception(f"Training Q&A error: {e}")
        return jsonify({"error": "Failed to generate answer"}), 500


# --- quiz: where is the AI seller in its script, and what should it do next ---


@bp.route("/quiz/question", methods=["GET"])
def quiz_question():
    """Get a quiz question for the specified type"""

    session_bot, error = require_session()
    if error:
        return error

    quiz_type = request.args.get("type", "stage")
    question = get_quiz_question(quiz_type)

    return jsonify(
        {
            "success": True,
            "question": question,
            "type": quiz_type,
            **bot_state(session_bot),
        }
    )


def _required_text(field: str, label: str):
    """A stripped required text field from the JSON body, or an error response."""
    value = ((request.json or {}).get(field) or "").strip()
    if not value:
        return None, (jsonify({"error": f"{label} required"}), 400)
    if len(value) > MAX_MESSAGE_LENGTH:
        return None, (jsonify({"error": f"{label} too long"}), 400)
    return value, None


@bp.route("/quiz/stage", methods=["POST"])
def quiz_stage():
    """Stage identification quiz (deterministic evaluation)"""
    session_bot, error = require_session()
    if error:
        return error
    answer, error = _required_text("answer", "Answer")
    if error:
        return error

    result = session_bot.run_quiz_stage_answer(answer)
    return jsonify({"success": True, **result, **bot_state(session_bot)})


@bp.route("/quiz/next-move", methods=["POST"])
def quiz_next_move():
    """Next move quiz (LLM-evaluated comparison)"""
    session_bot, error = require_session()
    if error:
        return error
    response, error = _required_text("response", "Response")
    if error:
        return error

    result = session_bot.run_quiz_next_move(response)
    return jsonify({"success": True, **result, **bot_state(session_bot)})


@bp.route("/quiz/direction", methods=["POST"])
def quiz_direction():
    """Direction/strategy quiz (LLM-evaluated understanding check)"""
    session_bot, error = require_session()
    if error:
        return error
    explanation, error = _required_text("explanation", "Explanation")
    if error:
        return error

    result = session_bot.run_quiz_direction(explanation)
    return jsonify({"success": True, **result, **bot_state(session_bot)})
