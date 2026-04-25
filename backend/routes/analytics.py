"""Analytics, quiz and knowledge management endpoints"""

import json
from datetime import datetime
from pathlib import Path
from threading import Lock

from flask import Blueprint, jsonify, request

from core.analytics.session_analytics import SessionAnalytics
from ..security import (
    InputValidator,
    require_rate_limit,
    require_strict_admin_token,
)
from core.knowledge import (
    ALLOWED_FIELDS,
    MAX_FIELD_LENGTH,
    clear_custom_knowledge,
    load_custom_knowledge,
    save_custom_knowledge,
)
from core.quiz import get_quiz_question
from ..security import SecurityConfig

bp = Blueprint("analytics", __name__, url_prefix="/api")


def init_routes(app, require_session_func, bot_state_func=None):
    """Initialize analytics routes with Flask app and callback functions"""
    bp.app = app  # type: ignore[attr-defined]
    bp.require_session = require_session_func  # type: ignore[attr-defined]
    bp.bot_state = bot_state_func  # type: ignore[attr-defined]


@bp.route("/test/question", methods=["GET"])
def get_test_question():
    """Get a quiz question for the specified type"""

    session_bot, error = bp.require_session()  # type: ignore
    if error:
        return error

    quiz_type = request.args.get("type", "stage")
    question = get_quiz_question(quiz_type)

    return jsonify(
        {
            "success": True,
            "question": question,
            "type": quiz_type,
            **bp.bot_state(session_bot),  # type: ignore[misc]
        }
    )


@bp.route("/test/stage", methods=["POST"])
def test_stage():
    """Stage identification quiz (deterministic evaluation)"""
    session_bot, error = bp.require_session()  # type: ignore
    if error:
        return error

    data = request.json or {}
    answer = (data.get("answer") or "").strip()
    if not answer:
        return jsonify({"error": "Answer required"}), 400
    if len(answer) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Answer too long"}), 400

    result = session_bot.run_quiz_stage_answer(answer)

    return jsonify({"success": True, **result, **bp.bot_state(session_bot)})  # type: ignore[misc]


@bp.route("/test/next-move", methods=["POST"])
def test_next_move():
    """Next move quiz (LLM-evaluated comparison)"""
    session_bot, error = bp.require_session()  # type: ignore
    if error:
        return error

    data = request.json or {}
    response = (data.get("response") or "").strip()
    if not response:
        return jsonify({"error": "Response required"}), 400
    if len(response) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Response too long"}), 400

    result = session_bot.run_quiz_next_move(response)

    return jsonify({"success": True, **result, **bp.bot_state(session_bot)})  # type: ignore[misc]


@bp.route("/test/direction", methods=["POST"])
def test_direction():
    """Direction/strategy quiz (LLM-evaluated understanding check)"""
    session_bot, error = bp.require_session()  # type: ignore
    if error:
        return error

    data = request.json or {}
    explanation = (data.get("explanation") or "").strip()
    if not explanation:
        return jsonify({"error": "Explanation required"}), 400
    if len(explanation) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Explanation too long"}), 400

    result = session_bot.run_quiz_direction(explanation)

    return jsonify({"success": True, **result, **bp.bot_state(session_bot)})  # type: ignore[misc]


@bp.route("/knowledge", methods=["GET"])
@require_rate_limit("knowledge")
def get_knowledge():
    """Retrieve current custom knowledge"""
    return jsonify({"success": True, "data": load_custom_knowledge()})


@bp.route("/knowledge", methods=["POST"])
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
@require_rate_limit("knowledge")
def clear_knowledge_route():
    """Clear all custom knowledge"""
    success = clear_custom_knowledge()
    return jsonify({"success": success})


@bp.route("/analytics/session/<session_id>", methods=["GET"])
def get_session_analytics(session_id):
    """Analytics events for a session. Caller's X-Session-ID header must match the path param"""
    caller_id = request.headers.get("X-Session-ID", "")
    caller_error = InputValidator.validate_session_id(caller_id)
    if caller_error:
        return caller_error
    path_error = InputValidator.validate_session_id(session_id)
    if path_error:
        return path_error
    if session_id != caller_id:
        return jsonify({"error": "Forbidden"}), 403
    events = SessionAnalytics.get_session_analytics(session_id)
    return jsonify({"success": True, "session_id": session_id, "events": events})


@bp.route("/analytics/summary", methods=["GET"])
@require_strict_admin_token
def get_analytics_summary():
    """Aggregated stats for the evaluation chapter. Same shape as get_evaluation_summary()"""
    summary = SessionAnalytics.get_evaluation_summary()
    return jsonify({"success": True, **summary})


_FEEDBACK_FILE = str(Path(__file__).resolve().parents[2] / "feedback.jsonl")
_feedback_lock = Lock()


@bp.route("/feedback", methods=["POST"])
@require_rate_limit("feedback")
def submit_feedback():
    """Append user feedback to feedback.jsonl. Never resets - append-only"""
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
