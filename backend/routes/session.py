"""Session lifecycle endpoints - init, restore, reset, health, config"""

import json
import logging
import secrets
from typing import Any

from flask import Blueprint, jsonify, request

from core.analytics.performance import PerformanceTracker
from core.seller_bot import SellerBot
from core.constants import UNDETERMINED_STAGE
from core.content import generate_init_greeting
from core.loader import QuickMatcher
from core.script_engine.seller import selling_config
from core.providers import get_available_providers
from .. import settings
from ._utils import validate_provider, with_session
from ..messages import (
    SERVER_FULL,
    BOT_INIT_FAILED,
    invalid_stage,
    invalid_strategy,
    STRATEGY_SWITCH_FAILED,
)
from ..security import (
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
    require_session_func,
):
    """Initialize session routes with Flask app and callback functions"""
    bp.app = app  # type: ignore
    bp.session_manager = session_manager_obj  # type: ignore
    bp.get_session = get_session_func  # type: ignore
    bp.require_session = require_session_func  # type: ignore
    bp.set_session = set_session_func  # type: ignore
    bp.delete_session = delete_session_func  # type: ignore
    bp.bot_state = bot_state_func  # type: ignore


@bp.route("/init", methods=["POST"])
@require_rate_limit("init")
def api_init():
    """Initialize or restore an in-memory session. Creates bot eagerly to avoid first-message latency."""
    data = request.json or {}
    existing_id = data.get("session_id")

    # Restore existing session only if it is still in memory on this process.
    if existing_id:
        session_error = InputValidator.validate_session_id(existing_id)
        if session_error:
            return session_error
        bot = bp.get_session(existing_id)  # type: ignore
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
    )  # None → selling.yaml default_product (scripted call)
    user_message = data.get("user_message", "")
    provider, provider_error = validate_provider(data)
    if provider_error:
        return provider_error

    # Auto-detect product from user message if not explicitly provided
    if (not product_type or product_type == "default") and user_message:
        detected_product, confidence = QuickMatcher.match_product(user_message)
        if detected_product and confidence >= 0.7:
            product_type = detected_product
            bp.app.logger.info(
                f"Auto-detected product: {product_type} (confidence: {confidence:.2f})"
            )  # type: ignore

    if not product_type or product_type == "default":
        product_type = selling_config().get("default_product")

    try:
        bot = SellerBot(
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
        bot.save_session()  # log the initial state snapshot for monitoring
        active_provider = getattr(bot, "provider_name", provider or "auto")
        bp.app.logger.info(
            f"New session: {session_id} "
            f"(product={product_type}, strategy={bot.flow_engine.flow_type}, provider={active_provider})"
        )  # type: ignore
    except Exception as init_error:
        bp.app.logger.exception(f"Bot init failed: {init_error}")  # type: ignore
        return jsonify(
            {"error": BOT_INIT_FAILED}
        ), 500

    # greeting + training blob, keep in sync with STRATEGY_PROMPTS
    init_data = generate_init_greeting(bot.flow_engine.flow_type)
    opening = bot.script_opening()  # a scripted call opens with the script's first line
    if opening:
        init_data = {**init_data, "message": opening}

    # Add greeting to conversation history so the LLM knows the conversation has started.
    # Without this, the LLM sees an empty history on the first user turn and re-greets.
    bot.flow_engine.conversation_history.append(
        {"role": "assistant", "content": init_data["message"]}
    )
    bp.app.logger.info(
        "conversation_turn %s",
        json.dumps(
            {
                "session_id": session_id,
                "turn_index": 0,
                "flow_type": bot.flow_engine.flow_type,
                "current_stage": bot.flow_engine.current_stage,
                "strategy": bot.flow_engine.flow_type,
                "user_message": None,
                "assistant_message": init_data["message"],
            },
            ensure_ascii=False,
        ),
    )
    bot.save_session()

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
            "success": True,
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
            "success": True,
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
            "strategies": ["consultative", "transactional"],
            "features": {
                "flow_controls_enabled": not settings.require_admin_for_stage_mutation(
                    bp.app.config  # type: ignore[attr-defined]
                ),
            },
        }
    )


@bp.route("/stages", methods=["GET"])
@with_session(bp)
def api_stages(bot):
    """Return available stages for the current session's flow"""
    stages = bot.flow_engine.flow_config.get("stages", [])
    return jsonify({"success": True, "stages": stages})


@bp.route("/stage", methods=["POST"])
@require_privileged_mutation
@with_session(bp)
def api_stage(bot):
    """Jump FSM to a specific stage. Admin/test only (requires privileged auth)."""
    from core.enums import Strategy

    data = request.json or {}
    stage = data.get("stage")

    # Validate stage against available stages
    stages = bot.flow_engine.flow_config.get("stages", [])
    if not stage or stage not in stages:
        return jsonify({"error": invalid_stage(stages)}), 400

    # Advance FSM to target stage
    bot.flow_engine.advance(target_stage=stage)

    stage_str = (
        UNDETERMINED_STAGE
        if bot.flow_engine.flow_type == Strategy.INTENT
        else bot.flow_engine.current_stage.upper()
    )

    bp.app.logger.info(f"Stage jumped to {stage}")  # type: ignore
    bot.save_session()  # Persist the stage change

    return jsonify(
        {"success": True, "stage": stage_str, "strategy": bot.flow_engine.flow_type.upper()}
    ), 200


@bp.route("/strategy", methods=["POST"])
@require_privileged_mutation
@with_session(bp)
def api_strategy(bot):
    """Switch FSM strategy for this session"""
    data = request.json or {}
    strategy = (data.get("strategy") or "").strip().lower()

    valid_strategies = {"intent", "consultative", "transactional"}
    if strategy not in valid_strategies:
        return jsonify(
            {"error": invalid_strategy(valid_strategies)}
        ), 400

    if not bot.flow_engine.switch_strategy(strategy):
        bp.app.logger.warning(f"Strategy switch failed to strategy {strategy}")  # type: ignore
        return jsonify({"error": STRATEGY_SWITCH_FAILED}), 400

    # Preserve the original reset baseline, but keep rewind snapshots aligned
    # with the current turn after this out-of-band strategy change.
    bot.refresh_current_turn_snapshot()
    bot.save_session()

    bp.app.logger.info(f"Strategy switched to {strategy}")  # type: ignore

    return jsonify({"success": True, **bp.bot_state(bot)})  # type: ignore


@bp.route("/reset", methods=["POST"])
@with_session(bp)
def reset(bot):
    """Delete the current session"""
    # Telemetry must never be the reason a learner cannot end their session.
    try:
        bot.record_session_end()
    except Exception:
        logger.exception("Could not record the end of this session")
    bp.delete_session(request.headers.get("X-Session-ID"))  # type: ignore
    return jsonify({"success": True})
