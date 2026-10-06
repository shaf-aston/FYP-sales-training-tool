"""Chat conversation endpoints - main chat, edit, summary, training"""

from flask import Blueprint, current_app, jsonify, request

from ._utils import bot_state, require_session, safe_latency_ms, validate_message
from ..messages import GENERIC_ERROR
from ..security import require_rate_limit

bp = Blueprint("chat", __name__, url_prefix="/api")


@bp.route("/chat", methods=["POST"])
@require_rate_limit("chat")
def chat():
    """Handle chat messages. Bot must be initialized via /api/init first"""

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
def edit_message():
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




@bp.route("/training/ask", methods=["POST"])
@require_rate_limit("chat")
def training_ask():
    """Answer a trainee's question about the conversation and sales techniques"""
    from ..security import SecurityConfig

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
    if len(question) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Question too long"}), 400

    try:
        result = session_bot.answer_training_question(question, style=style)
        return jsonify({"success": True, **result})
    except Exception as e:
        current_app.logger.exception(f"Training Q&A error: {e}")
        return jsonify({"error": "Failed to generate answer"}), 500
