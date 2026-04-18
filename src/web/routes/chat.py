"""Chat conversation endpoints — main chat, edit, summary, training"""

from flask import Blueprint, jsonify, request

from web.messages import GENERIC_ERROR
from web.security import require_rate_limit

bp = Blueprint("chat", __name__, url_prefix="/api")


def init_routes(
    app, get_session_func, require_session_func, validate_message_func, bot_state_func
):
    """hook up chat routes"""
    # Store dependencies in blueprint context
    bp.app = app  # type: ignore[attr-defined]
    bp.require_session = require_session_func  # type: ignore[attr-defined]
    bp.validate_message = validate_message_func  # type: ignore[attr-defined]
    bp.bot_state = bot_state_func  # type: ignore[attr-defined]


@bp.route("/chat", methods=["POST"])
@require_rate_limit("chat")
def chat():
    """Handle chat messages. Bot must be initialized via /api/init first"""

    data = request.json
    user_message, err = bp.validate_message(data.get("message", ""))  # type: ignore
    if err:
        return err

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    try:
        response = bot.chat(user_message)
        training = bot.generate_training(user_message, response.content)

        # Extract content and metrics from ChatResponse
        return jsonify(
            {
                "success": True,
                "message": response.content,
                **bp.bot_state(bot),  # type: ignore
                "latency_ms": round(response.latency_ms, 1),
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
        bp.app.logger.exception(f"Chat error: {e}")  # type: ignore
        return jsonify({"error": GENERIC_ERROR}), 500


@bp.route("/edit", methods=["POST"])
@require_rate_limit("chat")
def edit_message():
    """Edit user message and regenerate from that point"""
    data = request.json or {}
    msg_index = data.get("index")
    new_message, err = bp.validate_message(data.get("message", ""))  # type: ignore

    bot, bot_err = bp.require_session()  # type: ignore
    if bot_err:
        return bot_err

    if err:
        return err

    # Validate inputs
    if msg_index is None:
        return jsonify({"error": "Missing message index"}), 400

    try:
        msg_index = int(msg_index)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid index format"}), 400

    # Validate index is within bounds
    max_index = len(bot.flow_engine.conversation_history) - 1
    if msg_index < 0 or msg_index > max_index:
        return jsonify({"error": f"Invalid index. Valid range: 0-{max_index}"}), 400

    try:
        # Rewind to turn BEFORE the edit, then replay with new message
        turn_index = msg_index // 2  # Convert message index to turn index
        if not bot.rewind_to_turn(turn_index):
            return jsonify({"error": "Rewind failed"}), 500

        response = bot.chat(new_message)
        training = bot.generate_training(new_message, response.content)

        return jsonify(
            {
                "success": True,
                "message": response.content,
                "history": [
                    {"role": m["role"], "content": m["content"]}
                    for m in bot.flow_engine.conversation_history
                ],
                **bp.bot_state(bot),  # type: ignore
                "latency_ms": round(response.latency_ms, 1),
                "provider": response.provider,
                "model": response.model,
                "training": training,
            }
        )
    except Exception as e:
        bp.app.logger.exception(f"Edit error: {e}")  # type: ignore
        return jsonify({"error": "Couldn't apply that edit -- try again in a sec"}), 500


@bp.route("/summary", methods=["GET"])
def get_summary():
    """Get conversation summary"""
    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    return jsonify({"success": True, "summary": bot.get_conversation_summary()})


@bp.route("/training/ask", methods=["POST"])
@require_rate_limit("chat")
def training_ask():
    """Answer a trainee's question about the conversation and sales techniques"""
    from web.security import SecurityConfig

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

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
        result = bot.answer_training_question(question, style=style)
        return jsonify({"success": True, **result})
    except Exception as e:
        bp.app.logger.exception(f"Training Q&A error: {e}")  # type: ignore
        return jsonify({"error": "Failed to generate answer"}), 500
