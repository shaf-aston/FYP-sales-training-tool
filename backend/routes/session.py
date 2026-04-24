"""Session lifecycle endpoints - init, restore, reset, health, config"""

import logging
import secrets
from typing import Any

from flask import Blueprint, jsonify, request

from core.analytics.performance import PerformanceTracker
from core.chatbot import SalesChatbot
from core.content import generate_init_greeting
from core.loader import QuickMatcher
from core.providers import get_available_providers
from core.providers.factory import supported_provider_names
from ..messages import (
    SERVER_FULL, BOT_INIT_FAILED, INVALID_HISTORY_FORMAT, INVALID_HISTORY_ENTRY,
    SESSION_RESTORE_FAILED, SESSION_NOT_FOUND,
    invalid_stage, invalid_strategy, STRATEGY_SWITCH_FAILED, history_entry_too_long,
    SCORE_CALCULATION_FAILED
)
from ..security import (
    PromptInjectionValidator,
    SecurityConfig,
    InputValidator,
    has_valid_admin_token,
    require_privileged_mutation,
    require_rate_limit,
)

logger = logging.getLogger(__name__)

bp: Any = Blueprint("session", __name__, url_prefix="/api")


def init_routes(
    app,
    session_manager_obj,
    get_session_func,
    set_session_func,
    delete_session_func,
    bot_state_func,
):
    """Initialize session routes with Flask app and callback functions"""
    bp.app = app  # type: ignore
    bp.session_manager = session_manager_obj  # type: ignore
    bp.get_session = get_session_func  # type: ignore
    bp.set_session = set_session_func  # type: ignore
    bp.delete_session = delete_session_func  # type: ignore
    bp.bot_state = bot_state_func  # type: ignore


@bp.route("/init", methods=["POST"])
@require_rate_limit("init")
def api_init():
    """Initialize or restore session. Creates bot eagerly to avoid first-message latency"""
    data = request.json or {}
    existing_id = data.get("session_id")

    # Restore existing session if still alive on server
    if existing_id:
        session_error = InputValidator.validate_session_id(existing_id)
        if session_error:
            return session_error
        bot = bp.get_session(existing_id)  # type: ignore
        if not bot:
            # Try loading from disk if not in memory
            bot = SalesChatbot.load_session(existing_id)
            if bot:
                bp.set_session(existing_id, bot)  # type: ignore
                bp.app.logger.info(f"Restored session from disk: {existing_id}")  # type: ignore
        if bot:
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in bot.flow_engine.conversation_history
            ]
            bp.app.logger.info(
                f"Restored session: {existing_id} ({len(history)} messages)"
            )  # type: ignore
            return jsonify(
                {
                    "success": True,
                    "session_id": existing_id,
                    "message": None,
                    **bp.bot_state(bot),  # type: ignore
                    "history": history,
                }
            )

    # Session count ceiling: reject new sessions when server is full
    if not bp.session_manager.can_create():  # type: ignore
        bp.app.logger.warning(  # type: ignore
            f"Session cap ({SecurityConfig.MAX_SESSIONS}) reached - rejecting new init"
        )
        return jsonify(
            {"error": SERVER_FULL}
        ), 503

    # Create new session with eager bot initialization
    session_id = secrets.token_hex(16)
    product_type = data.get(
        "product_type"
    )  # None → generic default → intent-first discovery
    user_message = data.get("user_message", "")
    provider = InputValidator.normalize_provider(data.get("provider"))
    if provider is not None and provider not in supported_provider_names(include_non_production=False):
        return (
            jsonify(
                {
                    "error": "Unsupported provider",
                    "code": "UNSUPPORTED_PROVIDER",
                    "supported_providers": supported_provider_names(
                        include_non_production=False
                    ),
                }
            ),
            400,
        )

    # Auto-detect product from user message if not explicitly provided
    if (not product_type or product_type == "default") and user_message:
        detected_product, confidence = QuickMatcher.match_product(user_message)
        if detected_product and confidence >= 0.7:
            product_type = detected_product
            bp.app.logger.info(
                f"Auto-detected product: {product_type} (confidence: {confidence:.2f})"
            )  # type: ignore

    try:
        bot = SalesChatbot(
            provider_type=provider, product_type=product_type, session_id=session_id
        )
        # dev override - skip intent detection
        force_strategy = data.get("force_strategy")
        if force_strategy in ("consultative", "transactional"):
            if has_valid_admin_token(request, bp.app.config):  # type: ignore[attr-defined]
                bot.flow_engine.initial_flow_type = force_strategy
                bot.flow_engine.switch_strategy(force_strategy)
            else:
                bp.app.logger.warning(  # type: ignore[attr-defined]
                    "Ignored unauthorized force_strategy override for path %s",
                    request.path,
                )
        bp.set_session(session_id, bot)  # type: ignore
        active_provider = getattr(bot, "provider_name", provider or "auto")
        bp.app.logger.info(
            f"New session: {session_id} (product={product_type}, strategy={bot.flow_engine.flow_type}, provider={active_provider})"
        )  # type: ignore
    except Exception as init_error:
        bp.app.logger.exception(f"Bot init failed: {init_error}")  # type: ignore
        return jsonify(
            {"error": BOT_INIT_FAILED}
        ), 500

    # greeting + training blob, keep in sync with STRATEGY_PROMPTS
    init_data = generate_init_greeting(bot.flow_engine.flow_type)

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "message": init_data["message"],
            **bp.bot_state(bot),  # type: ignore
            "history": [],
            "training": init_data["training"],
        }
    )


@bp.route("/restore", methods=["POST"])
@require_rate_limit("init")
def api_restore():
    """Rebuild bot from client history after a server restart. No LLM calls"""
    data = request.json or {}
    history = data.get("history", [])  # [{role, content}, ...]
    product_type = data.get(
        "product_type"
    )  # None → generic default → intent-first discovery
    provider = InputValidator.normalize_provider(data.get("provider"))
    if provider is not None and provider not in supported_provider_names(include_non_production=False):
        return (
            jsonify(
                {
                    "error": "Unsupported provider",
                    "code": "UNSUPPORTED_PROVIDER",
                    "supported_providers": supported_provider_names(
                        include_non_production=False
                    ),
                }
            ),
            400,
        )

    # reject corrupted localStorage before replay
    if not isinstance(history, list):
        return jsonify({"error": INVALID_HISTORY_FORMAT}), 400
    for entry in history:
        if (
            not isinstance(entry, dict)
            or entry.get("role") not in ("user", "assistant")
            or not isinstance(entry.get("content"), str)
        ):
            return jsonify({"error": INVALID_HISTORY_ENTRY}), 400
    if len(history) % 2 != 0:
        return jsonify({"error": "History must contain complete user/assistant turns"}), 400
    for idx in range(0, len(history), 2):
        if history[idx].get("role") != "user" or history[idx + 1].get("role") != "assistant":
            return jsonify({"error": "History must alternate user and assistant turns"}), 400
    max_restore_entry_chars = SecurityConfig.MAX_MESSAGE_LENGTH * 4
    sanitized_history = []
    for entry in history:
        content = entry.get("content", "")
        if len(content) > max_restore_entry_chars:
            return jsonify(
                {
                    "error": history_entry_too_long(max_restore_entry_chars)
                }
            ), 400
        sanitized_history.append(
            {
                "role": entry["role"],
                "content": PromptInjectionValidator.sanitize(content),
            }
        )

    history = sanitized_history[-200:]

    session_id = secrets.token_hex(16)

    try:
        bot = SalesChatbot(
            provider_type=provider, product_type=product_type, session_id=session_id
        )

        # Replay history into bot - reconstructs FSM state and strategy switches
        if history:
            bot.replay(history)

        bp.set_session(session_id, bot)  # type: ignore
        bp.app.logger.info(
            f"Restored session: {session_id} ({len(history)} messages replayed)"
        )  # type: ignore

    except Exception as e:
        bp.app.logger.exception(f"Restore failed: {e}")  # type: ignore
        return jsonify(
            {
                "error": SESSION_RESTORE_FAILED
            }
        ), 500

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            **bp.bot_state(bot),  # type: ignore
        }
    )


@bp.route("/health", methods=["GET"])
def api_health():
    """Health check: provider availability and performance stats"""
    session_id = request.headers.get("X-Session-ID")

    # Get active provider info
    active_provider = None
    active_model = None
    if session_id:
        bot = bp.get_session(session_id)  # type: ignore
        if bot:
            active_provider = bot.provider_name
            active_model = bot.model_name

    # Get available providers
    provider_status = get_available_providers()

    # Get aggregate performance stats
    perf_stats = PerformanceTracker.get_provider_stats()

    return jsonify(
        {
            "ok": True,
            "active": {"provider": active_provider, "model": active_model},
            "available_providers": provider_status,
            "performance_stats": perf_stats,
        }
    )


@bp.route("/config", methods=["GET"])
def api_config():
    """Expose config metadata (products, limits, strategies) for the frontend"""
    from core.loader import load_product_config
    from ..security import SecurityConfig

    config = load_product_config()
    products = config.get("products", {})

    # Expose product options for frontend use
    product_strategies = {k: v.get("strategy", "intent") for k, v in products.items()}
    product_options = [
        {
            "id": k,
            "strategy": product_strategies[k],
            "label": v.get("name") or v.get("context") or k,
        }
        for k, v in products.items()
    ]

    return jsonify(
        {
            "ok": True,
            "limits": {
                "max_message_length": SecurityConfig.MAX_MESSAGE_LENGTH,
                "max_field_length": SecurityConfig.MAX_FIELD_LENGTH,
                "max_sessions": SecurityConfig.MAX_SESSIONS,
            },
            "rate_limits": {
                "init": {
                    "requests": SecurityConfig.RATE_LIMITS["init"][0],
                    "window_seconds": SecurityConfig.RATE_LIMITS["init"][1],
                },
                "chat": {
                    "requests": SecurityConfig.RATE_LIMITS["chat"][0],
                    "window_seconds": SecurityConfig.RATE_LIMITS["chat"][1],
                },
            },
            "product_options": product_options,
            "strategies": ["consultative", "transactional", "intent"],
            "features": {
                "flow_controls_enabled": not SecurityConfig.require_admin_for_stage_mutation(
                    bp.app.config  # type: ignore[attr-defined]
                ),
                "browser_tts_fallback_enabled": SecurityConfig.browser_tts_fallback_enabled(
                    bp.app.config  # type: ignore[attr-defined]
                ),
            },
        }
    )


@bp.route("/stages", methods=["GET"])
def api_stages():
    """Return available stages for the current session's flow"""
    session_id = request.headers.get("X-Session-ID")
    session_error = InputValidator.validate_session_id(session_id)
    if session_error:
        return session_error

    bot = bp.get_session(session_id)  # type: ignore
    if not bot:
        return jsonify({"error": SESSION_NOT_FOUND}), 404

    stages = bot.flow_engine.flow_config.get("stages", [])
    return jsonify({"success": True, "stages": stages})


@bp.route("/stage", methods=["POST"])
@require_privileged_mutation
def api_stage():
    """Jump FSM to a specific stage. Admin/test only (requires privileged auth)."""
    from core.utils import Strategy

    session_id = request.headers.get("X-Session-ID")
    session_error = InputValidator.validate_session_id(session_id)
    if session_error:
        return session_error

    bot = bp.get_session(session_id)  # type: ignore
    if not bot:
        return jsonify({"error": SESSION_NOT_FOUND}), 404

    data = request.json or {}
    stage = data.get("stage")

    # Validate stage against available stages
    stages = bot.flow_engine.flow_config.get("stages", [])
    if not stage or stage not in stages:
        return jsonify({"error": invalid_stage(stages)}), 400

    # Advance FSM to target stage
    bot.flow_engine.advance(target_stage=stage)

    # Format response: show "----" for intent-first discovery, otherwise stage name
    stage_str = (
        "----"
        if bot.flow_engine.flow_type == Strategy.INTENT
        else bot.flow_engine.current_stage.upper()
    )
    return jsonify(
        {"success": True, "stage": stage_str, "strategy": bot.flow_engine.flow_type.upper()}
    ), 200


@bp.route("/strategy", methods=["POST"])
@require_privileged_mutation
def api_strategy():
    """Switch FSM strategy for this session"""
    session_id = request.headers.get("X-Session-ID")
    session_error = InputValidator.validate_session_id(session_id)
    if session_error:
        return session_error

    bot = bp.get_session(session_id)  # type: ignore
    if not bot:
        return jsonify({"error": SESSION_NOT_FOUND}), 404

    data = request.json or {}
    strategy = (data.get("strategy") or "").strip().lower()

    valid_strategies = {"intent", "consultative", "transactional"}
    if strategy not in valid_strategies:
        return jsonify(
            {"error": invalid_strategy(valid_strategies)}
        ), 400

    if not bot.flow_engine.switch_strategy(strategy):
        return jsonify({"error": STRATEGY_SWITCH_FAILED}), 400

    # Keep rewind/reset behaviour consistent after explicit manual switches
    bot.flow_engine.initial_flow_type = strategy
    bot.save_session()

    return jsonify({"success": True, **bp.bot_state(bot)})  # type: ignore


@bp.route("/score", methods=["GET"])
def get_score():
    """Retrieve post-session performance score for the current roleplay session"""
    session_id = request.headers.get("X-Session-ID")
    session_error = InputValidator.validate_session_id(session_id)
    if session_error:
        return session_error

    bot = bp.get_session(session_id)  # type: ignore
    if not bot:
        return jsonify({"error": SESSION_NOT_FOUND}), 404

    from core.trainer import score_session

    try:
        assert isinstance(session_id, str)
        score_data = score_session(session_id)
        return jsonify({"success": True, "score": score_data})
    except Exception as e:
        logger.error(f"Error calculating session score: {e}")
        return jsonify({"error": SCORE_CALCULATION_FAILED}), 500


@bp.route("/reset", methods=["POST"])
def reset():
    """Delete the current session"""
    session_id = request.headers.get("X-Session-ID")
    session_error = InputValidator.validate_session_id(session_id)
    if session_error:
        return session_error

    bot = bp.get_session(session_id)  # type: ignore
    if not bot:
        return jsonify({"error": SESSION_NOT_FOUND}), 400

    bp.delete_session(session_id)  # type: ignore
    return jsonify({"success": True})
