"""Analytics, quiz, and knowledge management endpoints"""

import json
import os
from datetime import datetime
from threading import Lock

from flask import Blueprint, jsonify, request

from chatbot.analytics.session_analytics import SessionAnalytics
from web.security import require_privileged_mutation, require_rate_limit
from chatbot.knowledge import (
    ALLOWED_FIELDS,
    MAX_FIELD_LENGTH,
    clear_custom_knowledge,
    load_custom_knowledge,
    save_custom_knowledge,
)
from web.security import InputValidator, SecurityConfig

bp = Blueprint("analytics", __name__, url_prefix="/api")


def init_routes(app, require_session_func, bot_state_func=None):
    """hook up analytics routes"""
    bp.app = app  # type: ignore[attr-defined]
    bp.require_session = require_session_func  # type: ignore[attr-defined]
    bp.bot_state = bot_state_func  # type: ignore[attr-defined]


@bp.route("/test/question", methods=["GET"])
def get_test_question():
    """Get a quiz question for the specified type"""

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    quiz_type = request.args.get("type", "stage")
    from chatbot.quiz import get_quiz_question

    question = get_quiz_question(quiz_type)

    return jsonify(
        {
            "success": True,
            "question": question,
            "type": quiz_type,
            **bp.bot_state(bot),  # type: ignore[misc]
        }
    )


@bp.route("/test/stage", methods=["POST"])
def test_stage():
    """Stage identification quiz (deterministic evaluation)"""
    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    data = request.json or {}
    answer = (data.get("answer") or "").strip()
    if not answer:
        return jsonify({"error": "Answer required"}), 400
    if len(answer) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Answer too long"}), 400

    from chatbot.quiz import test_quiz_stage_answer

    result = test_quiz_stage_answer(answer, bot)

    return jsonify({"success": True, **result, **bp.bot_state(bot)})  # type: ignore[misc]


@bp.route("/test/next-move", methods=["POST"])
def test_next_move():
    """Next move quiz (LLM-evaluated comparison)"""
    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    data = request.json or {}
    response = (data.get("response") or "").strip()
    if not response:
        return jsonify({"error": "Response required"}), 400
    if len(response) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Response too long"}), 400

    # Get last user message from history for context
    history = bot.flow_engine.conversation_history
    last_user_msg = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    from chatbot.quiz import test_quiz_next_move

    result = test_quiz_next_move(response, bot, last_user_msg)

    return jsonify({"success": True, **result, **bp.bot_state(bot)})  # type: ignore[misc]


@bp.route("/test/direction", methods=["POST"])
def test_direction():
    """Direction/strategy quiz (LLM-evaluated understanding check)"""
    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    data = request.json or {}
    explanation = (data.get("explanation") or "").strip()
    if not explanation:
        return jsonify({"error": "Explanation required"}), 400
    if len(explanation) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Explanation too long"}), 400

    from chatbot.quiz import test_quiz_direction

    result = test_quiz_direction(explanation, bot)

    return jsonify({"success": True, **result, **bp.bot_state(bot)})  # type: ignore[misc]


@bp.route("/knowledge", methods=["GET"])
@require_privileged_mutation
@require_rate_limit("knowledge")
def get_knowledge():
    """Retrieve current custom knowledge"""
    return jsonify({"success": True, "data": load_custom_knowledge()})


@bp.route("/knowledge", methods=["POST"])
@require_privileged_mutation
@require_rate_limit("knowledge")
def save_knowledge_route():
    """Save custom knowledge data with field-level validation"""
    data = request.json or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid payload"}), 400

    error = InputValidator.validate_knowledge_data(
        data, allowed_fields=ALLOWED_FIELDS, max_field_length=MAX_FIELD_LENGTH
    )
    if error:
        return error

    success = save_custom_knowledge(data)
    return jsonify({"success": success})


@bp.route("/knowledge", methods=["DELETE"])
@require_privileged_mutation
@require_rate_limit("knowledge")
def clear_knowledge_route():
    """Clear all custom knowledge"""
    success = clear_custom_knowledge()
    return jsonify({"success": success})


@bp.route("/analytics/session/<session_id>", methods=["GET"])
def get_session_analytics(session_id):
    """Analytics events for a session. Caller's X-Session-ID header must match the path param"""
    caller_id = request.headers.get("X-Session-ID", "")
    if session_id != caller_id:
        return jsonify({"error": "Forbidden"}), 403
    events = SessionAnalytics.get_session_analytics(session_id)
    return jsonify({"success": True, "session_id": session_id, "events": events})


@bp.route("/analytics/summary", methods=["GET"])
def get_analytics_summary():
    """Aggregated stats for the evaluation chapter. Same shape as get_evaluation_summary()"""
    summary = SessionAnalytics.get_evaluation_summary()
    return jsonify({"success": True, **summary})


_FEEDBACK_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "feedback.jsonl"
)
_feedback_lock = Lock()


@bp.route("/feedback", methods=["POST"])
def submit_feedback():
    """Append user feedback to feedback.jsonl. Never resets — append-only"""
    data = request.json or {}
    rating = data.get("rating")
    comment = (data.get("comment") or "").strip()

    if not rating and not comment:
        return jsonify({"error": "Rating or comment required"}), 400

    if rating is not None:
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return jsonify({"error": "Rating must be 1-5"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "Rating must be a number 1-5"}), 400

    if comment and len(comment) > 500:
        bp.app.logger.debug("feedback comment trimmed to 500 chars")  # type: ignore
        comment = comment[:500]

    entry = {
        "timestamp": datetime.now().isoformat(),
        "rating": rating,
        "comment": comment or None,
        "page": data.get("page", "chat"),
    }

    with _feedback_lock:
        try:
            with open(_FEEDBACK_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except IOError as e:
            bp.app.logger.error(f"Failed to write feedback: {e}")  # type: ignore
            return jsonify({"error": "Failed to save feedback"}), 500

    return jsonify({"success": True})
