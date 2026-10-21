"""Replies read aloud, for both modes."""

from flask import Blueprint, Response, request

from core.constants import SPEECH
from core.providers.speech import speak

from ..security import require_rate_limit

bp = Blueprint("speech", __name__, url_prefix="/api")


@bp.route("/speech", methods=["POST"])
@require_rate_limit("speech")
def speech():
    """Audio for the text, or 204 so the browser uses its own voice."""
    audio = speak(str((request.get_json(silent=True) or {}).get("text", "")))
    return Response(audio, mimetype=f"audio/{SPEECH['format']}") if audio else Response(status=204)
