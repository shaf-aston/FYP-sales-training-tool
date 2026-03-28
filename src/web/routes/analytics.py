"""Analytics, quiz, and knowledge management endpoints."""

# pyright: ignore[reportGeneralTypeIssues]  # Flask Blueprint dynamic attribute injection

from flask import Blueprint, request, jsonify
from chatbot.session_analytics import SessionAnalytics
from chatbot.knowledge import load_custom_knowledge, save_custom_knowledge, clear_custom_knowledge, ALLOWED_FIELDS, MAX_FIELD_LENGTH

bp = Blueprint('analytics', __name__, url_prefix='/api')


def init_routes(app, require_session_func):
    """Initialize analytics routes with dependency injection.

    Args:
        app: Flask app (for logger access)
        require_session_func: Function to validate and return (bot, error)
    """
    bp.app = app  # type: ignore[attr-defined]
    bp.require_session = require_session_func  # type: ignore[attr-defined]


# ============================================================================
# Quiz/Assessment API
# ============================================================================

@bp.route('/quiz/question', methods=['GET'])
def quiz_get_question():
    """Get a quiz question for the specified type."""

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    quiz_type = request.args.get('type', 'stage')
    from chatbot.quiz import get_quiz_question
    question = get_quiz_question(quiz_type)

    # Extract bot state (inline to avoid circular dependency)
    from chatbot.utils import Strategy
    stage = "----" if bot.flow_engine.flow_type == Strategy.INTENT else bot.flow_engine.current_stage.upper()
    strategy = bot.flow_engine.flow_type.upper()

    return jsonify({
        "success": True,
        "question": question,
        "type": quiz_type,
        "stage": stage,
        "strategy": strategy,
    })


@bp.route('/quiz/stage', methods=['POST'])
def quiz_stage():
    """Stage identification quiz (deterministic evaluation)."""
    from web.security import SecurityConfig

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    data = request.json or {}
    answer = (data.get('answer') or '').strip()
    if not answer:
        return jsonify({"error": "Answer required"}), 400
    if len(answer) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Answer too long"}), 400

    from chatbot.quiz import evaluate_stage_quiz
    result = evaluate_stage_quiz(answer, bot)

    # Extract bot state
    from chatbot.utils import Strategy
    stage = "----" if bot.flow_engine.flow_type == Strategy.INTENT else bot.flow_engine.current_stage.upper()
    strategy = bot.flow_engine.flow_type.upper()

    return jsonify({"success": True, **result, "stage": stage, "strategy": strategy})


@bp.route('/quiz/next-move', methods=['POST'])
def quiz_next_move():
    """Next move quiz (LLM-evaluated comparison)."""
    from web.security import SecurityConfig

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    data = request.json or {}
    response = (data.get('response') or '').strip()
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

    from chatbot.quiz import evaluate_next_move_quiz
    result = evaluate_next_move_quiz(response, bot, last_user_msg)

    # Extract bot state
    from chatbot.utils import Strategy
    stage = "----" if bot.flow_engine.flow_type == Strategy.INTENT else bot.flow_engine.current_stage.upper()
    strategy = bot.flow_engine.flow_type.upper()

    return jsonify({"success": True, **result, "stage": stage, "strategy": strategy})


@bp.route('/quiz/direction', methods=['POST'])
def quiz_direction():
    """Direction/strategy quiz (LLM-evaluated understanding check)."""
    from web.security import SecurityConfig

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    data = request.json or {}
    explanation = (data.get('explanation') or '').strip()
    if not explanation:
        return jsonify({"error": "Explanation required"}), 400
    if len(explanation) > SecurityConfig.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "Explanation too long"}), 400

    from chatbot.quiz import evaluate_direction_quiz
    result = evaluate_direction_quiz(explanation, bot)

    # Extract bot state
    from chatbot.utils import Strategy
    stage = "----" if bot.flow_engine.flow_type == Strategy.INTENT else bot.flow_engine.current_stage.upper()
    strategy = bot.flow_engine.flow_type.upper()

    return jsonify({"success": True, **result, "stage": stage, "strategy": strategy})


# ============================================================================
# Knowledge API
# ============================================================================

@bp.route('/knowledge', methods=['GET'])
def get_knowledge():
    """Retrieve current custom knowledge."""
    return jsonify({"success": True, "data": load_custom_knowledge()})


@bp.route('/knowledge', methods=['POST'])
def save_knowledge_route():
    """Save custom knowledge data with field-level validation."""
    from web.security import InputValidator

    data = request.json

    # Validate knowledge data (type checking, field whitelisting, length limits)
    error = InputValidator.validate_knowledge_data(
        data,
        allowed_fields=ALLOWED_FIELDS,
        max_field_length=MAX_FIELD_LENGTH
    )
    if error:
        return error

    success = save_custom_knowledge(data)
    return jsonify({"success": success})


@bp.route('/knowledge', methods=['DELETE'])
def clear_knowledge_route():
    """Clear all custom knowledge."""
    success = clear_custom_knowledge()
    return jsonify({"success": success})


# ============================================================================
# Evaluation Analytics APIs
# ============================================================================

@bp.route('/analytics/session/<session_id>', methods=['GET'])
def get_session_analytics(session_id):
    """Get analytics events for a specific session (for evaluation study).

    Returns all recorded events: stage transitions, intent classifications,
    objection types, strategy switches.
    """
    events = SessionAnalytics.get_session_analytics(session_id)
    return jsonify({"success": True, "session_id": session_id, "events": events})


@bp.route('/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Get aggregated analytics summary for evaluation chapter.

    Returns:
    - stage_reach_distribution: how many sessions reached each stage
    - intent_distribution: frequency of low/medium/high classifications
    - objection_type_distribution: which objection types appear most
    - initial_strategy_distribution: consultative vs transactional assigned
    - strategy_switch_frequency: how often strategies changed
    - ab_variant_distribution: distribution across A/B variants
    - sessions_reached_pitch: count of sessions reaching pitch stage
    - sessions_reached_objection: count of sessions reaching objection stage
    - total_sessions: total session count
    """
    summary = SessionAnalytics.get_evaluation_summary()
    return jsonify({"success": True, **summary})
