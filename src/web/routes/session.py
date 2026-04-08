"""Session lifecycle endpoints — init, restore, reset, health, config."""

import logging

from flask import Blueprint, request, jsonify
import secrets
from chatbot.chatbot import SalesChatbot
from chatbot.providers import get_available_providers
from chatbot.analytics.performance import PerformanceTracker
from chatbot.content import generate_init_greeting
from chatbot.loader import QuickMatcher

logger = logging.getLogger(__name__)

bp = Blueprint('session', __name__, url_prefix='/api')


def init_routes(app, session_manager_obj, get_session_func, set_session_func, delete_session_func, bot_state_func):
    """Initialize session routes with dependency injection.

    Args:
        app: Flask app (for logger access)
        session_manager_obj: SessionSecurityManager instance
        get_session_func: Function to get session by ID
        set_session_func: Function to store session
        delete_session_func: Function to delete session
        bot_state_func: Function to extract bot state dict
    """
    bp.app = app  # type: ignore
    bp.session_manager = session_manager_obj  # type: ignore
    bp.get_session = get_session_func  # type: ignore
    bp.set_session = set_session_func  # type: ignore
    bp.delete_session = delete_session_func  # type: ignore
    bp.bot_state = bot_state_func  # type: ignore


@bp.route('/init', methods=['POST'])
def api_init():
    """Initialize or restore session. Creates bot eagerly to avoid first-message latency."""
    data = request.json or {}
    existing_id = data.get('session_id')

    # Restore existing session if still alive on server
    if existing_id:
        bot = bp.get_session(existing_id)  # type: ignore
        if not bot:
            # Try loading from disk if not in memory
            bot = SalesChatbot.load_session(existing_id)
            if bot:
                bp.set_session(existing_id, bot)  # type: ignore
                bp.app.logger.info(f"Restored session from disk: {existing_id}")  # type: ignore
        if bot:
            history = [{"role": m["role"], "content": m["content"]}
                       for m in bot.flow_engine.conversation_history]
            bp.app.logger.info(f"Restored session: {existing_id} ({len(history)} messages)")  # type: ignore
            return jsonify({
                "success": True,
                "session_id": existing_id,
                "message": None,
                **bp.bot_state(bot),  # type: ignore
                "history": history
            })

    # Session count ceiling: reject new sessions when server is full
    from web.security import SecurityConfig
    if not bp.session_manager.can_create():  # type: ignore
        bp.app.logger.warning(  # type: ignore
            f"Session cap ({SecurityConfig.MAX_SESSIONS}) reached — rejecting new init"
        )
        return jsonify({"error": "Server at capacity. Please try again later."}), 503

    # Create new session with eager bot initialization
    session_id = secrets.token_hex(16)
    product_type = data.get('product_type')  # None → generic default → intent-first discovery
    user_message = data.get('user_message', '')
    provider = data.get('provider', "groq")

    # Auto-detect product from user message if not explicitly provided
    if (not product_type or product_type == 'default') and user_message:
        detected_product, confidence = QuickMatcher.match_product(user_message)
        if detected_product and confidence >= 0.7:
            product_type = detected_product
            bp.app.logger.info(f"Auto-detected product: {product_type} (confidence: {confidence:.2f})")  # type: ignore

    try:
        bot = SalesChatbot(provider_type=provider, product_type=product_type, session_id=session_id)
        # Dev: override strategy, skipping intent-detection phase entirely
        force_strategy = data.get('force_strategy')
        if force_strategy in ("consultative", "transactional"):
            bot.flow_engine._initial_flow_type = force_strategy
            bot.flow_engine.switch_strategy(force_strategy)
        bp.set_session(session_id, bot)  # type: ignore
        bp.app.logger.info(f"New session: {session_id} (product={product_type}, strategy={bot.flow_engine.flow_type}, provider={provider})")  # type: ignore
    except Exception as init_error:
        bp.app.logger.exception(f"Bot init failed: {init_error}")  # type: ignore
        return jsonify({"error": "Initialization failed. Please try again."}), 500

    # Generate greeting and training data from content.py — synced with STRATEGY_PROMPTS
    init_data = generate_init_greeting(bot.flow_engine.flow_type)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "message": init_data["message"],
        **bp.bot_state(bot),  # type: ignore
        "history": [],
        "training": init_data["training"],
    })


@bp.route('/restore', methods=['POST'])
def api_restore():
    """Rebuild bot from client-side history after server session loss.

    Accepts full conversation history from localStorage, replays into fresh bot
    to reconstruct FSM state without any LLM calls.
    """
    data = request.json or {}
    history = data.get('history', [])  # [{role, content}, ...]
    product_type = data.get('product_type')  # None → generic default → intent-first discovery
    provider = data.get('provider', "groq")

    # Validate history structure before replay to prevent corrupted localStorage crashing the bot
    if not isinstance(history, list):
        return jsonify({"error": "Invalid history format"}), 400
    for entry in history:
        if (not isinstance(entry, dict)
                or entry.get("role") not in ("user", "assistant")
                or not isinstance(entry.get("content"), str)):
            return jsonify({"error": "Invalid history entry"}), 400
    if len(history) > 200:
        history = history[-200:]

    session_id = secrets.token_hex(16)

    try:
        bot = SalesChatbot(provider_type=provider, product_type=product_type, session_id=session_id)

        # Replay history into bot — reconstructs FSM state and strategy switches
        if history:
            bot.replay(history)

        bp.set_session(session_id, bot)  # type: ignore
        bp.app.logger.info(f"Restored session: {session_id} ({len(history)} messages replayed)")  # type: ignore

    except Exception as e:
        bp.app.logger.exception(f"Restore failed: {e}")  # type: ignore
        return jsonify({"error": "Restore failed. Please retry."}), 500

    return jsonify({
        "success": True,
        "session_id": session_id,
        **bp.bot_state(bot),  # type: ignore
    })


@bp.route('/health', methods=['GET'])
def api_health():
    """Health check: provider availability and performance stats"""
    session_id = request.headers.get('X-Session-ID')

    # Get active provider info
    active_provider = None
    active_model = None
    if session_id:
        bot = bp.get_session(session_id)  # type: ignore
        if bot:
            active_provider = bot._provider_name
            active_model = bot._model_name

    # Get available providers
    provider_status = get_available_providers()

    # Get aggregate performance stats
    perf_stats = PerformanceTracker.get_provider_stats()

    return jsonify({
        "ok": True,
        "active": {
            "provider": active_provider,
            "model": active_model
        },
        "available_providers": provider_status,
        "performance_stats": perf_stats
    })


@bp.route('/config', methods=['GET'])
def api_config():
    """Expose system configuration metadata for frontend synchronization.

    Returns configuration limits, available products, and strategies
    so the frontend can validate input and guide users appropriately.
    """
    from chatbot.loader import load_product_config
    from web.security import SecurityConfig

    config = load_product_config()
    products = config.get('products', {})

    # Expose product options for frontend use while preserving the legacy
    # metadata shape used by existing callers.
    product_ids = list(products.keys())
    product_strategies = {
        k: v.get("strategy", "intent") for k, v in products.items()
    }
    product_options = [
        {
            "id": k,
            "strategy": product_strategies[k],
            "label": v.get("context", k),
        }
        for k, v in products.items()
    ]

    return jsonify({
        "ok": True,
        "limits": {
            "max_message_length": SecurityConfig.MAX_MESSAGE_LENGTH,
            "max_field_length": SecurityConfig.MAX_FIELD_LENGTH,
            "max_sessions": SecurityConfig.MAX_SESSIONS,
        },
        "rate_limits": {
            "init": {"requests": SecurityConfig.RATE_LIMITS["init"][0], "window_seconds": SecurityConfig.RATE_LIMITS["init"][1]},
            "chat": {"requests": SecurityConfig.RATE_LIMITS["chat"][0], "window_seconds": SecurityConfig.RATE_LIMITS["chat"][1]},
        },
        "products": {
            "available": product_ids,
            "default": "default",
        },
        "product_options": product_options,
        "product_strategies": product_strategies,
        "strategies": ["consultative", "transactional", "intent"],
    })


@bp.route('/score', methods=['GET'])
def get_score():
    """Retrieve post-session performance score for the current roleplay session."""
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400

    bot = bp.get_session(session_id)  # type: ignore
    if not bot:
        return jsonify({"error": "Session not found"}), 404

    from chatbot.training.trainer import score_session
    try:
        score_data = score_session(session_id)
        return jsonify({"success": True, "score": score_data})
    except Exception as e:
        logger.error(f"Error calculating session score: {e}")
        return jsonify({"error": "Failed to calculate score"}), 500


@bp.route('/reset', methods=['POST'])
def reset():
    """Delete the current session."""
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400

    bot = bp.get_session(session_id)  # type: ignore
    if not bot:
        return jsonify({"error": "Session not found"}), 400

    bp.delete_session(session_id)  # type: ignore
    return jsonify({"success": True})
