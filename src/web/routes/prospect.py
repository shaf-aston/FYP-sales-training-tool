"""Prospect mode endpoints — role-reversal where user plays salesperson."""

from flask import Blueprint, request, jsonify
import secrets

bp = Blueprint('prospect', __name__, url_prefix='/api/prospect')


def init_routes(app, prospect_session_manager_obj, validate_message_func):
    """Initialize prospect routes with dependency injection.

    Args:
        app: Flask app (for logger access)
        prospect_session_manager_obj: SessionSecurityManager instance for prospect sessions
        validate_message_func: Function to validate message text
    """
    bp.app = app  # type: ignore
    bp.prospect_session_manager = prospect_session_manager_obj  # type: ignore
    bp.validate_message = validate_message_func  # type: ignore


def _require_prospect_session():
    """Validate prospect session. Returns (prospect_session, error_response)."""
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        return None, (jsonify({"error": "Session ID required"}), 400)
    ps = bp.prospect_session_manager.get(session_id)  # type: ignore
    if not ps:
        return None, (jsonify({"error": "Prospect session not found", "code": "SESSION_EXPIRED"}), 400)
    return ps, None


@bp.route('/init', methods=['POST'])
def prospect_init():
    """Create a prospect session. Bot plays the buyer, user plays the salesperson."""
    if not bp.prospect_session_manager.can_create():  # type: ignore
        return jsonify({"error": "Prospect mode at capacity. Try again later."}), 503

    data = request.json or {}
    difficulty = data.get('difficulty', 'medium')
    product_type = data.get('product_type', 'default')
    provider = data.get('provider', 'groq')

    if difficulty not in ('easy', 'medium', 'hard'):
        return jsonify({"error": "Invalid difficulty. Choose: easy, medium, hard"}), 400

    session_id = secrets.token_hex(16)

    try:
        from chatbot.prospect.prospect import ProspectSession
        ps = ProspectSession(
            provider_type=provider,
            product_type=product_type,
            difficulty=difficulty,
            session_id=session_id,
        )
        opening = ps.get_opening_message()
        bp.prospect_session_manager.set(session_id, ps)  # type: ignore
        bp.app.logger.info(f"Prospect session: {session_id} (difficulty={difficulty}, product={product_type})")  # type: ignore

        return jsonify({
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
            "latency_ms": opening.latency_ms,
            "provider": opening.provider,
            "model": opening.model,
        })
    except Exception as e:
        bp.app.logger.exception(f"Prospect init failed: {e}")  # type: ignore
        return jsonify({"error": "Prospect init failed. Please retry."}), 500


@bp.route('/chat', methods=['POST'])
def prospect_chat():
    """User sends a sales message; prospect responds."""
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None

    data = request.json or {}
    user_message, val_err = bp.validate_message(data.get('message', ''))  # type: ignore
    if val_err:
        return val_err

    if ps.state.has_committed or ps.state.has_walked:
        return jsonify({"error": "Session has ended. Get evaluation or reset."}), 400

    show_hints = data.get('show_hints', False)

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
    except Exception as e:
        bp.app.logger.exception(f"Prospect chat error: {e}")  # type: ignore
        return jsonify({"error": "Prospect chat failed. Please retry."}), 500


@bp.route('/state', methods=['GET'])
def prospect_state():
    """Get current prospect session state."""
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None
    return jsonify({
        "success": True, 
        "state": ps.state.to_dict(),
        "persona": ps.persona,
        "difficulty": ps.state.difficulty,
        "product_type": ps.state.product_type,
        "conversation_history": ps.conversation_history,
        "provider": ps.provider_name,
        "model": ps.model_name
    })


@bp.route('/evaluate', methods=['POST'])
def prospect_evaluate():
    """Generate final evaluation scorecard."""
    ps, err = _require_prospect_session()
    if err:
        return err
    assert ps is not None

    try:
        evaluation = ps.get_evaluation()
        return jsonify({"success": True, **evaluation})
    except Exception as e:
        bp.app.logger.exception(f"Prospect evaluation error: {e}")  # type: ignore
        return jsonify({"error": "Evaluation failed. Please retry."}), 500


@bp.route('/reset', methods=['POST'])
def prospect_reset():
    """End and remove a prospect session."""
    session_id = request.headers.get('X-Session-ID')
    if session_id:
        bp.prospect_session_manager.delete(session_id)  # type: ignore
    return jsonify({"success": True})
