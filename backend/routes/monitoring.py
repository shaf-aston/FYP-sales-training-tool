"""Monitoring endpoints shared by both modes: health and feedback."""

import os
import subprocess

from flask import Blueprint, current_app, jsonify, request

from core.infra.constants import MAX_FEEDBACK_COMMENT_CHARS, MAX_FEEDBACK_PAGE_CHARS
from core.infra.logs import save_feedback
from core.infra.providers import get_available_providers

from ..messages import FEEDBACK_EMPTY, RATING_NOT_NUMBER, RATING_OUT_OF_RANGE
from ..security import require_rate_limit


def _version() -> str:
    """The git commit this server runs, so a deploy can check it is live."""
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=5, cwd=os.path.dirname(__file__)).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


VERSION = _version()

bp = Blueprint("monitoring", __name__, url_prefix="/api")


@bp.route("/health", methods=["GET"])
def api_health():
    """Health check: provider availability and the learner's active provider."""
    session_id = request.headers.get("X-Session-ID")

    active_provider = None
    active_model = None
    if session_id:
        seller = current_app.extensions["sessions"].seller.get(session_id)
        if seller:
            active_provider = seller.provider_name
            active_model = seller.model_name

    provider_status = get_available_providers()

    return jsonify(
        {
            "success": True,
            "version": VERSION,
            "active": {"provider": active_provider, "model": active_model},
            "available_providers": provider_status,
        }
    )


@bp.route("/feedback", methods=["POST"])
@require_rate_limit("feedback")
def submit_feedback():
    """Check the learner's rating/comment, then keep it in the feedback stream."""
    data = request.json or {}
    rating = data.get("rating")
    comment = (data.get("comment") or "").strip()

    if not rating and not comment:
        return jsonify({"error": FEEDBACK_EMPTY}), 400

    if rating is not None:
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return jsonify({"error": RATING_OUT_OF_RANGE}), 400
        except (TypeError, ValueError):
            return jsonify({"error": RATING_NOT_NUMBER}), 400

    if len(comment) > MAX_FEEDBACK_COMMENT_CHARS:
        current_app.logger.debug("feedback comment trimmed to %d chars", MAX_FEEDBACK_COMMENT_CHARS)
        comment = comment[:MAX_FEEDBACK_COMMENT_CHARS]

    save_feedback(rating=rating, comment=comment or None, page=str(data.get("page", "buy"))[:MAX_FEEDBACK_PAGE_CHARS])

    return jsonify({"success": True})
