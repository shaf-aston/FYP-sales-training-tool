"""Monitoring endpoints shared by both modes: health, session analytics, feedback."""

import json
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from core.analytics.performance import PerformanceTracker
from core.analytics.session_analytics import SessionAnalytics
from core.providers import get_available_providers

from ..security import InputValidator, require_rate_limit

bp = Blueprint("monitoring", __name__, url_prefix="/api")


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
def get_analytics_summary():
    """Aggregated stats for the evaluation chapter. Same shape as get_evaluation_summary()"""
    summary = SessionAnalytics.get_evaluation_summary()
    return jsonify({"success": True, **summary})


@bp.route("/feedback", methods=["POST"])
@require_rate_limit("feedback")
def submit_feedback():
    """Log user feedback for monitoring."""
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
        current_app.logger.debug("feedback comment trimmed to 500 chars")
        comment = comment[:500]

    entry = {
        "timestamp": datetime.now().isoformat(),
        "rating": rating,
        "comment": comment or None,
        "page": data.get("page", "buy"),
    }

    current_app.logger.info("feedback_event %s", json.dumps(entry, ensure_ascii=False))

    return jsonify({"success": True})
