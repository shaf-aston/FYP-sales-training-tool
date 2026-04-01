"""Chat conversation endpoints — main chat, edit, summary, training."""

from flask import Blueprint, request, jsonify

bp = Blueprint('chat', __name__, url_prefix='/api')


def init_routes(app, get_session_func, require_session_func, validate_message_func, bot_state_func):
    """Initialize chat routes with dependency injection.

    Args:
        app: Flask app (for logger access)
        get_session_func: Function to get chatbot session by ID
        require_session_func: Function to validate and return (bot, error)
        validate_message_func: Function to validate message text
        bot_state_func: Function to extract bot state dict
    """
    # Store dependencies in blueprint context
    bp.app = app  # type: ignore[attr-defined]
    bp.require_session = require_session_func  # type: ignore[attr-defined]
    bp.validate_message = validate_message_func  # type: ignore[attr-defined]
    bp.bot_state = bot_state_func  # type: ignore[attr-defined]


@bp.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages. Bot must be initialized via /api/init first."""

    data = request.json
    user_message, err = bp.validate_message(data.get('message', ''))  # type: ignore
    if err:
        return err

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    try:
        response = bot.chat(user_message)
        training = bot.generate_training(user_message, response.content)

        # Extract content and metrics from ChatResponse
        return jsonify({
            "success": True,
            "message": response.content,
            **bp.bot_state(bot),  # type: ignore
            "latency_ms": round(response.latency_ms, 1),
            "provider": response.provider,
            "model": response.model,
            "metrics": {
                "input_length": response.input_len,
                "output_length": response.output_len
            },
            "training": training,
        })

    except Exception as e:
        bp.app.logger.exception(f"Chat error: {e}")  # type: ignore
        return jsonify({"error": "Chat request failed. Please retry."}), 500


@bp.route('/edit', methods=['POST'])
def edit_message():
    """Edit user message and regenerate from that point"""
    data = request.json or {}
    msg_index = data.get('index')
    new_message, err = bp.validate_message(data.get('message', ''))  # type: ignore

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

        return jsonify({
            "success": True,
            "message": response.content,
            "history": [{"role": m["role"], "content": m["content"]} for m in bot.flow_engine.conversation_history],
            **bp.bot_state(bot),  # type: ignore
            "latency_ms": round(response.latency_ms, 1),
            "provider": response.provider,
            "model": response.model,
            "training": training,
        })
    except Exception as e:
        bp.app.logger.exception(f"Edit error: {e}")  # type: ignore
        return jsonify({"error": "Edit failed. Please retry."}), 500


@bp.route('/summary', methods=['GET'])
def get_summary():
    """Get conversation summary"""
    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    return jsonify({
        "success": True,
        "summary": bot.get_conversation_summary()
    })


@bp.route('/training/ask', methods=['POST'])
def training_ask():
    """Answer a trainee's question about the conversation and sales techniques."""
    from web.security import SecurityConfig

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    data = request.json or {}
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({"error": "Question required"}), 400
    if len(question) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Question too long"}), 400

    try:
        result = bot.answer_training_question(question)
        return jsonify({"success": True, **result})
    except Exception as e:
        bp.app.logger.exception(f"Training Q&A error: {e}")  # type: ignore
        return jsonify({"error": "Failed to generate answer"}), 500
