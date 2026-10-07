"""Session lifecycle endpoints - init, restore, reset, health"""

import logging
import secrets

from flask import Blueprint, current_app, jsonify, request

from core.analytics.performance import PerformanceTracker
from core.seller_bot import SellerBot
from core.providers import get_available_providers
from ._utils import bot_state, validate_provider, with_session
from ..messages import SERVER_FULL, BOT_INIT_FAILED
from ..security import SecurityConfig, InputValidator, require_rate_limit

logger = logging.getLogger(__name__)

bp = Blueprint("session", __name__, url_prefix="/api")


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
        bot = current_app.extensions["sessions"].seller.get(existing_id)
        if bot:
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in bot.flow_engine.conversation_history
            ]
            current_app.logger.info(
                f"Restored session: {existing_id} ({len(history)} messages)"
            )
            return jsonify(
                {
                    "success": True,
                    "session_id": existing_id,
                    "message": None,
                    **bot_state(bot),
                    "history": history,
                }
            )

    # Session count ceiling: reject new sessions when server is full
    if not current_app.extensions["sessions"].seller.can_create():
        current_app.logger.warning(
            f"Session cap ({SecurityConfig.MAX_SESSIONS}) reached - rejecting new init"
        )
        return jsonify(
            {"error": SERVER_FULL}
        ), 503

    # Create new session with eager bot initialization
    session_id = secrets.token_hex(16)
    product_type = data.get("product_type")  # unlisted or missing → selling.yaml default_product
    provider, provider_error = validate_provider(data)
    if provider_error:
        return provider_error

    try:
        bot = SellerBot(
            provider_type=provider, product_type=product_type, session_id=session_id
        )
        current_app.extensions["sessions"].seller.set(session_id, bot)
        bot.save_session()  # log the initial state snapshot for monitoring
        active_provider = getattr(bot, "provider_name", provider or "auto")
        current_app.logger.info(
            f"New session: {session_id} "
            f"(product={bot.product_type}, provider={active_provider})"
        )
    except Exception as init_error:
        current_app.logger.exception(f"Bot init failed: {init_error}")
        return jsonify(
            {"error": BOT_INIT_FAILED}
        ), 500

    opening = bot.script_opening()
    bot.open_with(opening)

    return jsonify(
        {
            "success": True,
            "session_id": session_id,
            "message": opening,
            **bot_state(bot),
            "history": [],
            "training": bot.generate_training("", opening),
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
        bot = current_app.extensions["sessions"].seller.get(session_id)
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


@bp.route("/reset", methods=["POST"])
@with_session
def reset(bot):
    """Delete the current session"""
    # Telemetry must never be the reason a learner cannot end their session.
    try:
        bot.record_session_end()
    except Exception:
        logger.exception("Could not record the end of this session")
    current_app.extensions["sessions"].seller.delete(request.headers.get("X-Session-ID"))
    return jsonify({"success": True})
